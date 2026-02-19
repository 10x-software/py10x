import pytest

from core_10x.environment_variables import EnvVars
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


@pytest.mark.parametrize(['truth','values'],[[True,['1','2','-1','True',"'quoted'"]],[False,['0','False',"''"]],[None,['','Random']]])
def test_env_vars_converts_bool_true(monkeypatch,truth,values):
    for value in values:
        for v in (value,str(value).lower()):
            monkeypatch.setenv('XX_USE_TS_STORE_TRANSACTIONS', v)
            object.__getattribute__(EnvVars, 'use_ts_store_transactions').fget.clear()
            if truth is None:
                with pytest.raises(TypeError):
                    _ = EnvVars.use_ts_store_transactions
            else:
                assert EnvVars.use_ts_store_transactions is truth, f"Expected {v} to convert to {truth}"
