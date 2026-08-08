from core_10x.exec_control import CONVERT_VALUES_ON
from xxcommon.rdate import RDate

from xxfin.ccy import Ccy
from xxfin.dev_data_helpers.data_creator import DataCreator
from xxfin.mkt_conventions import BIZDAY_ROLL_RULE, FinCalendar

data = (
    dict(
        name                    = 'USD',
        bank_calendar           = 'FD|',

        settle_offset           = RDate('2B'),                  ## default
        spot_offset             = RDate('2B'),                  ## default
        roll_rule               = BIZDAY_ROLL_RULE.FOLLOWING,   ## default

        is_deliverable          = True,                         ## default
        discounting_mkt_name    = 'SOFR',
    ),
    dict(
        name                    = 'GBP',
        bank_calendar           = 'GB|',

        settle_offset           = RDate('2B'),                  ## default
        spot_offset             = RDate('2B'),                  ## default
        roll_rule               = BIZDAY_ROLL_RULE.FOLLOWING,   ## default

        is_deliverable          = True,                         ## default
        discounting_mkt_name    = 'SONIA',
    ),
    dict(
        name                    = 'EUR',
        bank_calendar           = 'EUTA|',

        settle_offset           = RDate('2B'),                  ## default
        spot_offset             = RDate('2B'),                  ## default
        roll_rule               = BIZDAY_ROLL_RULE.FOLLOWING,   ## default

        is_deliverable          = True,                         ## default
        discounting_mkt_name    = 'ESTR',
    ),
    dict(
        name                    = 'CHF',
        bank_calendar           = 'SZ|',   ## changed to bbg
        discounting_mkt_name    = 'SARON',
    ),
    dict(
        name                    = 'AUD',
        bank_calendar           = 'AU|',
        discounting_mkt_name    = 'AONIA',
    ),
    dict(
        name                    = 'NZD',
        bank_calendar           = 'NZ|',
        discounting_mkt_name    = 'NZIONA',   ## 'NZOCR', ??
    ),
    dict(
        name                    = 'CAD',
        bank_calendar           = 'CA|',
        discounting_mkt_name    = 'CORRA',
    ),
    dict(
        name                    = 'JPY',
        bank_calendar           = 'JP|',
        discounting_mkt_name    = 'TONA',
    ),

)

def run():
    with CONVERT_VALUES_ON():
        DataCreator.create(Ccy, data)

if __name__ == '__main__':
    run()


