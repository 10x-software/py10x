from xxcommon.rdate import RDate

from xxfin.dev_data_helpers.data_creator import DataCreator
from xxfin.fx_mkt_conventions import DAY_COUNT_CONVENTION, FXMktConventions

data = (
    dict(
        mkt_name            = 'GBP/USD',
        dc_convention       = DAY_COUNT_CONVENTION.ACT365,
        spot_offset         = RDate('2B'),
        settle_offset       = RDate('2B'),
    ),
    dict(
        mkt_name            = 'EUR/USD',
        spot_offset         = RDate('2B'),
        settle_offset       = RDate('2B'),
),
    dict(
        mkt_name            = 'AUD/USD',
        spot_offset         = RDate('2B'),
        settle_offset       = RDate('2B'),
    ),
    dict(
        mkt_name            = 'NZD/USD',
        spot_offset         = RDate('2B'),
        settle_offset       = RDate('2B'),
    ),
    dict(
        mkt_name            = 'USD/CHF',
        spot_offset         = RDate('2B'),
        settle_offset       = RDate('2B'),
    ),
    dict(
        mkt_name            = 'USD/CAD',
        spot_offset         = RDate('1B'),
        settle_offset       = RDate('1B'),
    ),
    dict(
        mkt_name            = 'USD/JPY',
        spot_offset         = RDate('2B'),
        settle_offset       = RDate('2B'),
    ),
)

def run():
    DataCreator.create(FXMktConventions, data)

if __name__ == '__main__':
    run()
