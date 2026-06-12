from core_10x.exec_control import CONVERT_VALUES_ON
from core_10x.traitable import T
from core_10x.traitable_cli import TraitableCli


class Cli(TraitableCli):
    """Master parser - the root command."""
    verbose: bool = T(False)


class Add(Cli, _command = 'add'):
    a: float = T(0.)
    b: float = T(0.)

    def result(self) -> float:
        return self.a + self.b


class Greet(Cli, _command = 'greet'):
    name: str = T('world')

    def message(self) -> str:
        return f'hello, {self.name}'


def show(args: list) -> None:
    rc, obj = Cli.instance_from_args(args)
    print(f'\nargs = {args!r}')
    if not rc:
        print(f'  ERROR: {rc.error()}')
        return

    print(f'  -> {type(obj).__name__}: {obj.serialize_object()}')
    if isinstance(obj, Add):
        print(f'  result = {obj.result()}')
    elif isinstance(obj, Greet):
        print(f'  message = {obj.message()}')


if __name__ == '__main__':
    (ctx:=CONVERT_VALUES_ON()).begin_using()
    # master command, no sub-command (boolean shortcuts + explicit value)
    show(['--verbose'])
    show(['--no-verbose'])
    show(['--verbose', 'true'])

    # 'add' sub-command with --option value pairs
    show(['add', '--a', '2', '--b', '3'])
    show(['add', '--a', '10', '--b', '40'])

    # 'greet' sub-command
    show(['greet', '--name', 'Sasha'])
    show(['greet'])

    # error cases
    show(['bogus'])
    show(['add', '--unknown', '1'])
    show(['--', 'oops'])
