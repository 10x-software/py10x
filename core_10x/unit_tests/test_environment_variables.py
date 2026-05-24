import pytest

from core_10x.environment_variables import EnvVars, _EnvVars
from core_10x.xdate_time import XDateTime, date


def test_env_vars_date_format_applies_to_xdatetime(monkeypatch):
    # Change via environment variable and ensure it is applied on first access
    custom_fmt = '%d/%m/%Y'
    monkeypatch.setenv('XX_DATE_FORMAT', custom_fmt)

    # Accessing EnvVars.date_format should convert and apply to XDateTime
    fmt = EnvVars.date_format
    assert fmt == custom_fmt

    d = date(2024, 1, 2)
    assert XDateTime.date_to_str(d) == '02/01/2024'


@pytest.mark.parametrize(['truth', 'values'], [[True, ['1', '2', '-1', 'True', "'quoted'"]], [False, ['0', 'False', "''"]], [None, ['', 'Random']]])
def test_env_vars_converts_bool_true(monkeypatch, truth, values):
    for value in values:
        for v in (value, str(value).lower()):
            monkeypatch.setenv('XX_USE_TS_STORE_TRANSACTIONS', v)
            object.__getattribute__(EnvVars, 'use_ts_store_transactions').fget.clear()
            if truth is None:
                with pytest.raises(TypeError):
                    _ = EnvVars.use_ts_store_transactions
            else:
                assert EnvVars.use_ts_store_transactions is truth, f'Expected {v} to convert to {truth}'


# ---------------------------------------------------------------------------
# EnvVars.var accessor and Var.check()
# ---------------------------------------------------------------------------

class TestEnvVarsVarAccessor:
    def test_var_returns_var_instance(self):
        v = EnvVars.var.date_format
        assert isinstance(v, _EnvVars.Var)

    def test_var_value_matches_property(self):
        v = EnvVars.var.date_format
        assert v.value == EnvVars.date_format

    def test_var_bool_true_for_non_empty(self, monkeypatch):
        monkeypatch.setenv('XX_DATE_FORMAT', '%Y/%m/%d')
        object.__getattribute__(EnvVars, 'date_format').fget.clear()
        v = EnvVars.var.date_format
        assert bool(v) is True

    def test_var_bool_false_for_empty_string(self, monkeypatch):
        monkeypatch.setenv('XX_MAIN_TS_STORE_URI', '')
        object.__getattribute__(EnvVars, 'main_ts_store_uri').fget.clear()
        v = EnvVars.var.main_ts_store_uri
        assert bool(v) is False

    def test_check_returns_value_when_truthy(self, monkeypatch):
        monkeypatch.setenv('XX_DATE_FORMAT', '%d-%m-%Y')
        object.__getattribute__(EnvVars, 'date_format').fget.clear()
        v = EnvVars.var.date_format
        assert v.check() == '%d-%m-%Y'

    def test_check_raises_value_error_when_falsy(self, monkeypatch):
        monkeypatch.setenv('XX_MAIN_TS_STORE_URI', '')
        object.__getattribute__(EnvVars, 'main_ts_store_uri').fget.clear()
        v = EnvVars.var.main_ts_store_uri
        with pytest.raises(ValueError, match='XX_MAIN_TS_STORE_URI'):
            v.check()

    def test_check_custom_error_message(self, monkeypatch):
        monkeypatch.setenv('XX_MAIN_TS_STORE_URI', '')
        object.__getattribute__(EnvVars, 'main_ts_store_uri').fget.clear()
        v = EnvVars.var.main_ts_store_uri
        with pytest.raises(ValueError, match='must be configured'):
            v.check(err='must be configured')

    def test_check_with_predicate_passes(self, monkeypatch):
        monkeypatch.setenv('XX_DATE_FORMAT', '%Y-%m-%d')
        object.__getattribute__(EnvVars, 'date_format').fget.clear()
        v = EnvVars.var.date_format
        result = v.check(f=lambda val: val.startswith('%'))
        assert result == '%Y-%m-%d'

    def test_check_with_predicate_raises_when_predicate_fails(self, monkeypatch):
        monkeypatch.setenv('XX_DATE_FORMAT', '%Y-%m-%d')
        object.__getattribute__(EnvVars, 'date_format').fget.clear()
        v = EnvVars.var.date_format
        with pytest.raises(ValueError, match='XX_DATE_FORMAT'):
            v.check(f=lambda val: val.startswith('!'), err='must start with !')
