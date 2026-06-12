import pytest
from core_10x.named_constant import Enum, ErrorCode
from core_10x.rc import RC, RC_TRUE, exc_to_rc


class CONDITION(Enum):
    BEGIN = ()
    MAIN = ()
    END = ()


class A_PROBLEM(ErrorCode):
    DOES_NOT_EXIST = 'Entity {cls}.{id} does not exist'
    REV_CONFLICT = 'Entity {cls}.{id} - revision {rev} is outdated'
    SAVE_FAILED = 'Failed to save entity {cls}.{id}'


# ----------------------------------------------------------------------------
#   Construction & truthiness
# ----------------------------------------------------------------------------

def test_bool_construction():
    assert RC(True)
    assert not RC(False)


def test_int_construction():
    assert RC(1)
    assert RC(42)
    assert not RC(0)
    assert not RC(-1)


def test_enum_construction_truthy():
    rc = RC(CONDITION.MAIN)
    assert rc
    assert rc.rc is CONDITION.MAIN


def test_error_code_is_falsy():
    rc = RC(A_PROBLEM.DOES_NOT_EXIST)
    assert not rc


def test_construction_with_data():
    rc = RC(True, 'hello')
    assert rc
    assert rc.payload == ['hello']


def test_construction_without_data_has_empty_payload():
    rc = RC(True)
    assert rc.payload == []


# ----------------------------------------------------------------------------
#   unwrap / data
# ----------------------------------------------------------------------------

def test_unwrap():
    rc = RC(True, 'data')
    code, payload = rc.unwrap()
    assert code is True
    assert payload == ['data']


def test_data_single_item():
    rc = RC(True, 123)
    assert rc.data() == 123


def test_data_multiple_items():
    rc = RC(True)
    rc.add_data(1)
    rc.add_data(2)
    rc.add_data(3)
    assert rc.data() == [1, 2, 3]


# ----------------------------------------------------------------------------
#   add_data
# ----------------------------------------------------------------------------

def test_add_data_to_success():
    rc = RC(True)
    rc.add_data('a')
    rc.add_data('b')
    assert rc
    assert rc.payload == ['a', 'b']


def test_add_data_to_error_fails():
    rc = RC(False, 'oops')
    with pytest.raises(AssertionError):
        rc.add_data('x')


# ----------------------------------------------------------------------------
#   add_error
# ----------------------------------------------------------------------------

def test_add_error_str_flips_to_failure():
    rc = RC(True)
    assert rc
    rc.add_error('something broke')
    assert not rc
    assert rc.rc is False
    assert 'something broke' in rc.error()


def test_add_error_multiple_strings():
    rc = RC(True)
    rc.add_error('first')
    rc.add_error('second')
    assert not rc
    err = rc.error()
    assert 'first' in err and 'second' in err


def test_add_error_with_truthy_rc_is_noop():
    rc = RC(True)
    rc.add_error(RC(True))
    assert rc
    assert rc.payload == []


def test_add_error_with_failing_rc_extends_payload():
    rc = RC(True)
    failing = RC(False, 'inner error')
    rc.add_error(failing)
    assert not rc
    assert 'inner error' in rc.error()


def test_add_error_invalid_type_raises():
    rc = RC(True)
    with pytest.raises(ValueError):
        rc.add_error(123)


def test_iadd_alias_for_add_error():
    rc = RC(True)
    rc += 'failure'
    assert not rc
    assert 'failure' in rc.error()


def test_ilshift_alias_for_add_error():
    rc = RC(True)
    rc <<= 'boom'
    assert not rc
    assert 'boom' in rc.error()


# ----------------------------------------------------------------------------
#   error()
# ----------------------------------------------------------------------------

def test_error_empty_for_success():
    assert RC(True).error() == ''
    assert RC(True, 'payload').error() == ''


def test_error_single_string():
    rc = RC(False, 'just an error')
    assert rc.error() == 'just an error'


def test_error_with_error_code_formats_label():
    rc = RC(A_PROBLEM.REV_CONFLICT, dict(cls='X', id='1', rev=3))
    msg = rc.error()
    assert 'X.1' in msg
    assert 'revision 3' in msg


def test_error_multiple_errors_joined():
    rc = RC(True)
    rc.add_error('one')
    rc.add_error('two')
    rc.add_error('three')
    msg = rc.error()
    assert msg.split('\n') == ['one', 'two', 'three']


def test_error_without_payload_returns_exception_info():
    try:
        raise RuntimeError('the cause')
    except RuntimeError:
        rc = RC(False)
        msg = rc.error()
    assert 'RuntimeError' in msg
    assert 'the cause' in msg


# ----------------------------------------------------------------------------
#   prepend_error_header
# ----------------------------------------------------------------------------

def test_prepend_error_header_on_failure():
    rc = RC(False, 'detail')
    rc.prepend_error_header('header')
    assert rc.payload == ['header', 'detail']
    assert rc.error().startswith('header')


def test_prepend_error_header_on_success_is_noop():
    rc = RC(True)
    rc.prepend_error_header('header')
    assert rc
    assert rc.payload == []


# ----------------------------------------------------------------------------
#   throw
# ----------------------------------------------------------------------------

def test_throw_on_success_does_nothing():
    RC(True).throw()
    RC(True, 'payload').throw()


def test_throw_default_runtime_error():
    rc = RC(False, 'bad')
    with pytest.raises(RuntimeError, match='bad'):
        rc.throw()


def test_throw_custom_exception():
    rc = RC(False, 'bad')
    with pytest.raises(ValueError, match='bad'):
        rc.throw(ValueError)


# ----------------------------------------------------------------------------
#   __add__ / __radd__ / sum
# ----------------------------------------------------------------------------

def test_add_two_truthy_rcs():
    rc = RC(True) + RC(True)
    assert rc


def test_add_truthy_and_failing():
    rc = RC(True) + RC(False, 'err')
    assert not rc
    assert 'err' in rc.error()


def test_add_does_not_change_lhs_truthiness():
    rc1 = RC(True)
    result = rc1 + RC(False, 'oops')
    assert not result
    # `__add__` returns a new RC; `rc1` itself stays truthy.
    assert rc1


def test_iadd_with_failing_rc():
    rc1 = RC(True)
    rc2 = RC(False, 'oops')
    rc1 += rc2
    assert not rc1
    assert 'oops' in rc1.error()


def test_iadd_with_truthy_rc():
    rc1 = RC(True)
    rc2 = RC(True)
    rc1 += rc2
    assert rc1
    assert rc2


def test_radd_with_zero_returns_self():
    rc = RC(True)
    assert (0 + rc) is rc


def test_sum_of_truthy():
    total = sum([RC_TRUE, RC(True), RC(True)])
    assert total


def test_sum_with_failure():
    total = sum([RC(True), RC(False, 'boom'), RC(True)])
    assert not total
    assert 'boom' in total.error()


# ----------------------------------------------------------------------------
#   new_rc / repr
# ----------------------------------------------------------------------------

def test_new_rc_returns_distinct_instance():
    rc = RC(True, 'a')
    other = rc.new_rc()
    assert other is not rc
    assert other
    assert other.rc == rc.rc


def test_repr_success_shows_payload():
    rc = RC(True, 'hello')
    assert 'hello' in repr(rc)


def test_repr_failure_shows_error():
    rc = RC(False, 'broken')
    assert 'broken' in repr(rc)


# ----------------------------------------------------------------------------
#   RC_TRUE constant
# ----------------------------------------------------------------------------

def test_rc_true_is_truthy():
    assert RC_TRUE
    assert RC_TRUE.rc is True


def test_rc_true_cannot_add_error():
    with pytest.raises(ValueError):
        RC_TRUE.add_error('cannot')


def test_rc_true_cannot_add_data():
    with pytest.raises(ValueError):
        RC_TRUE.add_data('cannot')


def test_rc_true_new_rc_returns_fresh_mutable_rc():
    rc = RC_TRUE.new_rc()
    assert rc is not RC_TRUE
    assert rc
    rc.add_error('now I am broken')
    assert not rc
    assert RC_TRUE


def test_rc_true_iadd_always_raises():
    # `+=` resolves to add_error, which is forbidden on the constant -
    # this is what protects the global RC_TRUE from being mutated.
    rc = RC_TRUE
    with pytest.raises(ValueError):
        rc += RC(True)
    with pytest.raises(ValueError):
        rc += 'anything'
    assert RC_TRUE
    assert RC_TRUE.payload == []


# ----------------------------------------------------------------------------
#   show_exception_info
# ----------------------------------------------------------------------------

def test_show_exception_info_from_active_exception():
    try:
        raise ValueError('explicit')
    except ValueError:
        info = RC.show_exception_info()
    assert 'ValueError' in info
    assert 'explicit' in info


def test_show_exception_info_invalid_input():
    with pytest.raises(AssertionError):
        RC.show_exception_info(ex_info=('not', 'a', 'valid', 'tuple'))


# ----------------------------------------------------------------------------
#   exc_to_rc
# ----------------------------------------------------------------------------

def test_exc_to_rc_returns_rc_true_on_success():
    @exc_to_rc
    def ok():
        return None

    rc = ok()
    assert rc is RC_TRUE


def test_exc_to_rc_with_message_returns_literal_error():
    def boom():
        raise ValueError('ignored detail')

    rc = exc_to_rc(boom, message='planned failure')()
    assert not rc
    assert rc.error() == 'planned failure'


def test_exc_to_rc_without_message_captures_exception_info():
    @exc_to_rc
    def boom():
        raise ValueError('kaboom')

    rc = boom()
    assert not rc
    err = rc.error()
    assert 'ValueError' in err
    assert 'kaboom' in err
