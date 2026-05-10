"""Tests for VaultUtils.verify_new_password — the pure validation logic that
requires no external I/O and is fully exercisable without mocking.

The heavier vault flows (user_init, admin_save_user_credentials, …) are
covered by test_user_onboarding.py which uses the vault_env fixture.
"""
import pytest

from core_10x.vault_utils import VaultUtils


MIN = VaultUtils.MIN_CHARS  # 8


# ----------------------------------------------------------------------------
#   Valid passwords
# ----------------------------------------------------------------------------

def test_valid_password_is_accepted():
    rc = VaultUtils.verify_new_password('ValidPass1', 'ValidPass1')
    assert rc


def test_valid_password_exactly_min_length():
    pwd = 'Abcdef1!'   # 8 chars, upper, lower, digit
    # Digits-only check uses isdigit(), symbol '!' passes the letter check? No.
    # 'Abcdef1!' has 'A' (upper), letters, digit '1'.
    rc = VaultUtils.verify_new_password(pwd, pwd)
    assert rc


def test_valid_password_longer_than_minimum():
    pwd = 'SuperSecure123'
    rc = VaultUtils.verify_new_password(pwd, pwd)
    assert rc


# ----------------------------------------------------------------------------
#   Empty / None passwords
# ----------------------------------------------------------------------------

def test_empty_password_is_rejected():
    rc = VaultUtils.verify_new_password('', '')
    assert not rc
    assert 'empty' in rc.error().lower()


def test_one_empty_password_is_rejected():
    rc = VaultUtils.verify_new_password('ValidPass1', '')
    assert not rc


# ----------------------------------------------------------------------------
#   Length requirement
# ----------------------------------------------------------------------------

@pytest.mark.parametrize('length', range(1, MIN))
def test_password_too_short_is_rejected(length):
    # Build a string that meets all other requirements but is too short.
    # Use 'Aa1' padded to the requested length with 'a'.
    base = 'Aa1'
    if length < len(base):
        # Just use a short stub — it will still fail the length check.
        pwd = ('A' + 'a' * (length - 2) + '1') if length >= 3 else 'Aa1'[:length]
    else:
        pwd = 'Aa1' + 'a' * (length - len(base))
    rc = VaultUtils.verify_new_password(pwd, pwd)
    assert not rc
    assert 'characters' in rc.error()


def test_password_of_min_length_passes_length_check():
    pwd = 'A' + 'a' * (MIN - 2) + '1'   # upper + (n-2) lowers + digit = n chars
    rc = VaultUtils.verify_new_password(pwd, pwd)
    assert rc


# ----------------------------------------------------------------------------
#   Missing letter
# ----------------------------------------------------------------------------

def test_no_letter_in_password_is_rejected():
    pwd = '1' * MIN   # all digits
    rc = VaultUtils.verify_new_password(pwd, pwd)
    assert not rc
    assert 'letter' in rc.error().lower()


# ----------------------------------------------------------------------------
#   Missing uppercase letter
# ----------------------------------------------------------------------------

def test_no_uppercase_is_rejected():
    pwd = 'password1'   # 9 chars, all lowercase + digit
    rc = VaultUtils.verify_new_password(pwd, pwd)
    assert not rc
    assert 'capital' in rc.error().lower()


# ----------------------------------------------------------------------------
#   Missing digit
# ----------------------------------------------------------------------------

def test_no_digit_is_rejected():
    pwd = 'PasswordA'   # 9 chars, upper + lower, no digit
    rc = VaultUtils.verify_new_password(pwd, pwd)
    assert not rc
    assert 'digit' in rc.error().lower()


# ----------------------------------------------------------------------------
#   Passwords do not match
# ----------------------------------------------------------------------------

def test_mismatched_passwords_are_rejected():
    rc = VaultUtils.verify_new_password('ValidPass1', 'ValidPass2')
    assert not rc
    assert 'match' in rc.error().lower()


def test_mismatch_reported_even_when_password_is_strong():
    rc = VaultUtils.verify_new_password('ValidPass1!', 'ValidPass1?')
    assert not rc
    assert 'match' in rc.error().lower()


# ----------------------------------------------------------------------------
#   Error header is prepended when there are errors
# ----------------------------------------------------------------------------

def test_error_header_prepended_on_failure():
    rc = VaultUtils.verify_new_password('bad', 'bad')
    assert not rc
    assert 'New password cannot be used' in rc.error()


def test_no_error_header_on_success():
    rc = VaultUtils.verify_new_password('ValidPass1', 'ValidPass1')
    assert rc
    assert rc.error() == ''


# ----------------------------------------------------------------------------
#   Multiple errors reported together
# ----------------------------------------------------------------------------

def test_multiple_errors_reported():
    rc = VaultUtils.verify_new_password('bad', 'different')
    assert not rc
    error = rc.error()
    assert 'characters' in error     # too short
    assert 'capital' in error        # no uppercase
    assert 'digit' in error          # no digit
    assert 'match' in error          # passwords don't match
