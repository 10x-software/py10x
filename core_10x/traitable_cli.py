import sys

from core_10x.traitable import RC, RC_TRUE, RT, Traitable


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
        Creates an instance of target traitable parsing positional args to obtain the right target class and then taking trait values
        in the name = value pairs form.
        One can use any spacing around symbol '=', i.e.: name=value name= value name =value or name = value

        :return:    (rc, traitable) - RC and a traitable according to args and trait values parsed from sys.argv.
                    rc holds error message(s) if instantiation fails for any reason (traitable is set to None)
        """
        script, *args = sys.argv
        return cls.instance_from_args(args)

    @classmethod
    def instance_from_args(cls, input_args: tuple) -> tuple:
        args = []
        trait_values = {}
        rc = cls.parse(input_args, args, trait_values)
        if not rc:
            return (rc, None)

        return cls.instantiate(args, trait_values)

    @classmethod
    def instantiate(cls, args, trait_values: dict) -> tuple:  # -- (RC, target_traitable)
        if not args:
            try:
                res = cls()
                trait: RT
                for name, value in trait_values.items():
                    trait = cls.trait(name)
                    if not trait:
                        return (RC(False, f'unknown attribute {name}\nValid attributes: {", ".join(cls.s_dir)}'), None)

                    rc = res.set_value(trait, value)
                    if not rc:
                        return (RC(False, f'{name}: {rc.err()}'), None)

                return (RC_TRUE, res)

            except Exception as ex:
                return (RC(False, str(ex)), None)

        command, *args = args
        parser = cls.s_switch.get(command)
        if not parser or not issubclass(parser, TraitableCli):
            return (RC(False, f'Unknown argument {command}'), None)

        return parser.instantiate(args, trait_values)

    @classmethod
    def parse(cls, input_args: tuple, args: list, trait_values: dict) -> RC:
        if not input_args:
            return RC_TRUE

        trait_name = None
        deal_with_args = True
        new_vp = True
        eq_expected = False
        for i, arg in enumerate(input_args):
            if deal_with_args:
                parts = arg.split('=', 1)
                n = len(parts)
                if n == 1:
                    args.append(arg)
                else:
                    deal_with_args = False
                    eq_expected = False
                    first, second = parts
                    if not first and not second:  # -- just '='
                        if i:
                            trait_name = args.pop(-1)
                            new_vp = False
                        else:
                            return RC(False, 'May not start with "="')

                    elif first:
                        if not second:  # -- xxx=
                            trait_name = first
                            new_vp = False
                        else:  # -- xxx=yyy
                            trait_values[first] = second
                            new_vp = True
                    else:  # -- =yyy
                        if i:
                            trait_name = args.pop(-1)
                            trait_values[trait_name] = second
                            new_vp = True
                        else:
                            return RC(False, 'May not start with "="')

            else:
                parts = arg.split('=', 1)
                n = len(parts)
                if new_vp:
                    trait_name = parts[0]
                    if n == 1:
                        eq_expected = True
                        new_vp = False
                    else:
                        value = parts[1]
                        if value:
                            trait_values[trait_name] = value
                            new_vp = True
                        else:
                            eq_expected = False
                            new_vp = False
                else:
                    if not eq_expected:
                        if n == 2:
                            return RC(False, f'Invalid "=": {input_args[i - 1]} {arg}')

                        trait_values[trait_name] = parts[0]
                        new_vp = True

                    else:
                        if n == 1:
                            return RC(False, f'"=" is expected before {arg}')

                        if parts[0]:
                            return RC(False, f'{input_args[i - 1]} {arg}')

                        if parts[1]:
                            trait_values[trait_name] = parts[1]
                            new_vp = True

                        else:
                            eq_expected = False

        if not new_vp:
            return RC(False, f'Value is missing for {trait_name} = ')

        return RC_TRUE
