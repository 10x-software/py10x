import pytest

from core_10x.exec_control import CONVERT_VALUES_ON
from core_10x.traitable import T
from core_10x.traitable_cli import TraitableCli


# ----------------------------------------------------------------------------
#   Test command hierarchy
# ----------------------------------------------------------------------------

class Cli(TraitableCli):
    """Master parser - the root command."""
    verbose: bool = T(False)


class Add(Cli, _command = 'add'):
    a: float = T(0.)
    b: float = T(0.)


class Greet(Cli, _command = 'greet'):
    name: str = T('world')


# ----------------------------------------------------------------------------
#   parse() - splitting argv into positional args and name = value pairs
# ----------------------------------------------------------------------------

def _parse(input_args):
    args, trait_values = [], {}
    rc = TraitableCli.parse(input_args, args, trait_values)
    return rc, args, trait_values


def test_parse_empty_args():
    rc, args, tv = _parse([])
    assert rc
    assert args == []
    assert tv == {}


def test_parse_positional_only():
    rc, args, tv = _parse(['add', 'sub'])
    assert rc
    assert args == ['add', 'sub']
    assert tv == {}


def test_parse_joined_pair():
    rc, args, tv = _parse(['a=2', 'b=3'])
    assert rc
    assert args == []
    assert tv == {'a': '2', 'b': '3'}


def test_parse_spaced_equals():
    # name = value  (three separate argv tokens)
    rc, args, tv = _parse(['a', '=', '10', 'b', '=', '40'])
    assert rc
    assert args == []
    assert tv == {'a': '10', 'b': '40'}


def test_parse_name_eq_then_value():
    # 'name='  'value'
    rc, args, tv = _parse(['name=', 'value'])
    assert rc
    assert tv == {'name': 'value'}


def test_parse_name_then_eq_value():
    # 'name'  '=value'
    rc, args, tv = _parse(['name', '=value'])
    assert rc
    assert args == []
    assert tv == {'name': 'value'}


def test_parse_positional_then_pairs():
    rc, args, tv = _parse(['add', 'a=2', 'b=3'])
    assert rc
    assert args == ['add']
    assert tv == {'a': '2', 'b': '3'}


# ----------------------------------------------------------------------------
#   parse() - error conditions
# ----------------------------------------------------------------------------

def test_parse_may_not_start_with_equals():
    rc, _, _ = _parse(['=oops'])
    assert not rc
    assert 'May not start with "="' in rc.error()


def test_parse_may_not_start_with_bare_equals():
    rc, _, _ = _parse(['=', 'value'])
    assert not rc
    assert 'May not start with "="' in rc.error()


def test_parse_missing_value():
    rc, _, _ = _parse(['name='])
    assert not rc
    assert 'Value is missing' in rc.error()


# ----------------------------------------------------------------------------
#   instance_from_args() - routing to the right command class
# ----------------------------------------------------------------------------

def test_instantiate_master_no_subcommand():
    with CONVERT_VALUES_ON():
        rc, obj = Cli.instance_from_args(['verbose=true'])
    assert rc
    assert type(obj) is Cli
    assert obj.verbose is True


def test_instantiate_subcommand_add():
    with CONVERT_VALUES_ON():
        rc, obj = Cli.instance_from_args(['add', 'a=2', 'b=3'])
    assert rc
    assert type(obj) is Add
    assert obj.a == 2.0
    assert obj.b == 3.0


def test_instantiate_subcommand_uses_defaults():
    with CONVERT_VALUES_ON():
        rc, obj = Cli.instance_from_args(['greet'])
    assert rc
    assert type(obj) is Greet
    assert obj.name == 'world'


def test_instantiate_subcommand_spaced_equals():
    with CONVERT_VALUES_ON():
        rc, obj = Cli.instance_from_args(['add', 'a', '=', '10', 'b', '=', '40'])
    assert rc
    assert obj.a == 10.0
    assert obj.b == 40.0


# ----------------------------------------------------------------------------
#   instance_from_args() - error conditions
# ----------------------------------------------------------------------------

def test_instantiate_unknown_command():
    rc, obj = Cli.instance_from_args(['bogus'])
    assert not rc
    assert obj is None
    assert 'Unknown argument bogus' in rc.error()


def test_instantiate_unknown_attribute():
    rc, obj = Cli.instance_from_args(['unknown=1'])
    assert not rc
    assert obj is None
    assert 'unknown attribute unknown' in rc.error()


def test_instantiate_propagates_parse_error():
    rc, obj = Cli.instance_from_args(['=oops'])
    assert not rc
    assert obj is None
    assert 'May not start with "="' in rc.error()


# ----------------------------------------------------------------------------
#   __init_subclass__ - command registration & validation
# ----------------------------------------------------------------------------

def test_subcommands_registered_on_master():
    assert Cli.s_switch['add'] is Add
    assert Cli.s_switch['greet'] is Greet


def test_master_may_not_have_command():
    with pytest.raises(AssertionError):
        class BadMaster(TraitableCli, _command = 'oops'):
            pass


def test_command_must_be_identifier():
    with pytest.raises(AssertionError):
        class BadCommand(Cli, _command = 'not an id'):
            pass
