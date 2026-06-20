import pytest

from core_10x.exec_control import CONVERT_VALUES_OFF
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
#   parse() - splitting argv into positional args and --option value pairs
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


def test_parse_option_value_pairs():
    rc, args, tv = _parse(['--a', '2', '--b', '3'])
    assert rc
    assert args == []
    assert tv == {'a': '2', 'b': '3'}


def test_parse_dashes_become_underscores():
    # --some-option -> trait some_option
    rc, args, tv = _parse(['--dry-run', 'true', '--max-retries', '5'])
    assert rc
    assert args == []
    assert tv == {'dry_run': 'true', 'max_retries': '5'}


def test_parse_boolean_shortcut_true():
    # --flag (followed by another option) is equivalent to --flag true
    rc, args, tv = _parse(['--verbose', '--name', 'x'])
    assert rc
    assert args == []
    assert tv == {'verbose': 'true', 'name': 'x'}


def test_parse_boolean_shortcut_true_at_end():
    rc, args, tv = _parse(['--verbose'])
    assert rc
    assert tv == {'verbose': 'true'}


def test_parse_boolean_shortcut_no_option():
    # --no-option is equivalent to --option false
    rc, args, tv = _parse(['--no-verbose', '--no-dry-run'])
    assert rc
    assert tv == {'verbose': 'false', 'dry_run': 'false'}


def test_parse_positional_then_options():
    rc, args, tv = _parse(['add', '--a', '2', '--b', '3'])
    assert rc
    assert args == ['add']
    assert tv == {'a': '2', 'b': '3'}


def test_parse_negative_number_value():
    # a single-dash token is a value, not an option
    rc, args, tv = _parse(['--a', '-3'])
    assert rc
    assert tv == {'a': '-3'}


# ----------------------------------------------------------------------------
#   parse() - error conditions
# ----------------------------------------------------------------------------

def test_parse_bare_double_dash():
    rc, _, _ = _parse(['--', 'value'])
    assert not rc
    assert 'Option name is missing' in rc.error()


# ----------------------------------------------------------------------------
#   instance_from_args() - routing to the right command class
# ----------------------------------------------------------------------------

def test_instantiate_master_no_subcommand():
    # instance_from_args() converts string tokens to trait types on its own.
    rc, obj = Cli.instance_from_args(['--verbose', 'true'])
    assert rc
    assert type(obj) is Cli
    assert obj.verbose is True


def test_instantiate_master_boolean_shortcut():
    # --verbose (no value) is equivalent to --verbose true
    rc, obj = Cli.instance_from_args(['--verbose'])
    assert rc
    assert type(obj) is Cli
    assert obj.verbose is True


def test_instantiate_master_no_boolean_shortcut():
    # --no-verbose is equivalent to --verbose false
    rc, obj = Cli.instance_from_args(['--no-verbose'])
    assert rc
    assert type(obj) is Cli
    assert obj.verbose is False


def test_instantiate_subcommand_add():
    rc, obj = Cli.instance_from_args(['add', '--a', '2', '--b', '3'])
    assert rc
    assert type(obj) is Add
    assert obj.a == 2.0
    assert obj.b == 3.0


def test_instantiate_subcommand_uses_defaults():
    rc, obj = Cli.instance_from_args(['greet'])
    assert rc
    assert type(obj) is Greet
    assert obj.name == 'world'


def test_instantiate_forces_conversion_inside_convert_off():
    # instance_from_args() turns value conversion on itself, overriding the surrounding context.
    with CONVERT_VALUES_OFF():
        rc, obj = Cli.instance_from_args(['add', '--a', '2', '--b', '3'])
    assert rc
    assert obj.a == 2.0
    assert obj.b == 3.0


# ----------------------------------------------------------------------------
#   instance_from_args() - error conditions
# ----------------------------------------------------------------------------

def test_instantiate_unknown_command():
    rc, obj = Cli.instance_from_args(['bogus'])
    assert not rc
    assert obj is None
    assert 'Unknown argument bogus' in rc.error()


def test_instantiate_unknown_attribute():
    rc, obj = Cli.instance_from_args(['--unknown', '1'])
    assert not rc
    assert obj is None
    assert 'unknown attribute unknown' in rc.error()


def test_instantiate_propagates_parse_error():
    rc, obj = Cli.instance_from_args(['--', 'oops'])
    assert not rc
    assert obj is None
    assert 'Option name is missing' in rc.error()


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
