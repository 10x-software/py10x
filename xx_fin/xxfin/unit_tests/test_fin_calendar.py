import pytest
from core_10x.exec_control import DEBUG_ON
from infra_10x.duckdb_store import DuckDbStore
from py10x_kernel import BTraitableProcessor

from xxfin.fin_calendar import FinCalendar


def test_save():
    with BTraitableProcessor.create_root(), DuckDbStore():
        assert not FinCalendar.existing_instance(name='US', _throw=False)
        with pytest.raises(ValueError, match=r'.*Instance does not exist.*'):
            FinCalendar.from_str('US|')
        with BTraitableProcessor.create_root():
            cal = FinCalendar(name='US')
            assert cal._rev == 0
            cal.save().throw()
            assert cal._rev == 1

        # cal = FinCalendar(name='US')
        cal = FinCalendar.existing_instance(name='US')
        assert cal.non_working_days
        assert cal.is_set(cal.T.non_working_days.trait)

        assert cal == FinCalendar.from_str('US|')
