import sys

from core_10x.exec_control import CONVERT_VALUES_ON
from core_10x.traitable import RC, RC_TRUE, Traitable


class TraitableCli(Traitable):
    s_master = None
    s_switch = {}

    def __init_subclass__(cls, _command: str = None, **kwargs):
        cls.s_switch = {}
        if cls.s_master is None:  # -- master parser
            assert _command is None, 'master may not have a command'
            cls.s_master = cls
        else:  # -- subordinate parser
            assert _command and _command.isidentifier(), 'command must be a valid identifier'
            cls.s_master.s_switch[_command] = cls
            cls.s_master = cls

        super().__init_subclass__(**kwargs)

    @classmethod
    def from_command_line(cls) -> tuple:  # -- (RC, Traitable)
        """
        Creates an instance of the target traitable: positional words select the target class and the
        remaining `--option value` pairs supply trait values.

        Option syntax (see :meth:`parse`):
            --option value      set trait `option` to `value`
            --some-option v     dashes in the name become underscores -> trait `some_option`
            --flag              boolean shortcut, equivalent to `--flag true`
            --no-flag           boolean shortcut, equivalent to `--flag false`

        :return:    (rc, traitable) - RC and a traitable according to args and trait values parsed from sys.argv.
                    rc holds error message(s) if instantiation fails for any reason (traitable is set to None)
        """
        _script, *args = sys.argv
        return cls.instance_from_args(args)

    @classmethod
    def instance_from_args(cls, input_args: tuple) -> tuple:
        args = []
        trait_values = {}
        rc = cls.parse(input_args, args, trait_values)
        if not rc:
            return rc, None

        # -- CLI tokens are always strings, so convert them to the target trait types.
        with CONVERT_VALUES_ON():
            return cls.instantiate(args, trait_values)

    @classmethod
    def instantiate(cls, args, trait_values: dict) -> tuple:  # -- (RC, target_traitable)
        if not args:
            try:
                res = cls()
                for name, value in trait_values.items():
                    trait = cls.trait(name)
                    if not trait:
                        return RC(False, f'unknown attribute {name}\nValid attributes: {", ".join(cls.s_dir)}'), None

                    rc = res.set_trait_value(trait, value)
                    if not rc:
                        return RC(False, f'{name}: {rc.error()}'), None

                return RC_TRUE, res

            except Exception as ex:
                return RC(False, str(ex)), None

        command, *args = args
        parser = cls.s_switch.get(command)
        if not parser or not issubclass(parser, TraitableCli):
            return RC(False, f'Unknown argument {command}'), None

        return parser.instantiate(args, trait_values)

    @classmethod
    def parse(cls, input_args: tuple, args: list, trait_values: dict) -> RC:
        """
        Splits CLI tokens into positional command words (appended to `args`) and option values
        (collected into `trait_values`).

        Options are introduced by a `--` prefix; dashes in an option name are converted to
        underscores so that `--some-option` maps to the trait `some_option`. Three forms are
        accepted:

            --option value      set trait `option` to `value` (the following non-option token)
            --option            boolean shortcut, equivalent to `--option true`
            --no-option         boolean shortcut, equivalent to `--option false`

        A token that does not start with `--` is a positional word (a sub-command). Positional
        words must precede any option, since a value-taking option consumes the token that
        follows it.

        :return:    RC; holds an error message when an option name is malformed.
        """
        i, n = 0, len(input_args)
        while i < n:
            arg = input_args[i]
            if not arg.startswith('--'):  # -- positional command word
                args.append(arg)
                i += 1
                continue

            name = arg[2:]
            if not name:
                return RC(False, 'Option name is missing after "--"')

            # -- --no-option / --no_option: boolean negation shortcut (== --option false)
            if (name.startswith('no-') or name.startswith('no_')) and len(name) > 3:
                trait_values[name[3:].replace('-', '_')] = 'false'
                i += 1
                continue

            name = name.replace('-', '_')
            # -- a following non-option token is the value; otherwise this is a boolean --option (== true)
            if i + 1 < n and not input_args[i + 1].startswith('--'):
                trait_values[name] = input_args[i + 1]
                i += 2
            else:
                trait_values[name] = 'true'
                i += 1

        return RC_TRUE
