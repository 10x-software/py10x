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
