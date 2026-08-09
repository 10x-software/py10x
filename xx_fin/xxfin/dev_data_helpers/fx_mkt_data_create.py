from datetime import date

from xxcommon.rdate import RDate

from xxfin.dev_data_helpers.data_creator import DataCreator
from xxfin.fx_spot_fwd_quotable import FXForwardQuotable, FXSpotQuotable

fx_data = {
    date(2025, 10, 10): {
        'GBP/USD':   {
            #FXSpotQuotable:     (('0C',), (1.3174,)),  ## presence of the class matters, tenor is irrelevant
            FXSpotQuotable:     ((None,), (1.3174,)),  ## presence of the class matters, tenor is irrelevant
            FXForwardQuotable:  (
                ('1B',      '1W',   '1M',       '3M',       '6M',       '9M',       '12M',      '2Y',       '5Y',       '20Y'),
                (1.31739,   1.31738, 1.31735,   1.31742,    1.31745,    1.31725,    1.3165,     1.31157,    1.2989,     1.26649)
            )
        },
        'EUR/USD': {
            FXSpotQuotable:     ((None,), (1.16018,)),
            FXForwardQuotable:  (
                ('1B',      '1W',       '1M',       '3M',       '6M',       '9M',       '12M',      '2Y',       '5Y',       '10Y'   ),
                (1.16024,   1.16069,    1.16221,    1.16603,    1.17101,    1.17564,    1.1797,     1.19362,    1.23218,     1.30417)
            )
        },
        'USD/JPY': {
            # FXSpotQuotable:     ((None,), (153.46,)),       ## as of 022026
            FXSpotQuotable:     ((None,), (154.545,)),
            FXForwardQuotable:  (
                ('1B',    '1W',       '1M',   '3M',       '6M',       '9M',       '12M',      '2Y',   '5Y',       '10Y'  ),
                (154.5,  154.436,    154.08,  153.143,    151.949,    150.828,    149.818,    146.27, 135.655,    1.30417)
                # (150,    150,      150,    150,         150,         150,       150,        150,    130,         110)       ## TEST
                # (153.45, 153.37,    153.10,  152.32,    151.27,     150.28,     149.54,     146.77,  138.50,    124.85)     ## data as of 022026
            )
        },
        'USD/CHF': {
            FXSpotQuotable:     ((None,), (0.794675,)),
            FXForwardQuotable:  (
                ('1B',      '1W',       '1M',       '3M',       '6M',   '9M',   '12M',  '2Y',   '5Y'),
                (.79441,    .79404,     .79194,     .78631,     .77885, .77165, .76478, .73951, .67028)
            )
        },
        'USD/CAD': {
            FXSpotQuotable: ((None,), (1.3775,)),
            FXForwardQuotable: (
                ('1W',  '1M',   '3M',   '6M',   '9M',   '12M',  '2Y',   '5Y'),
                ( 1.377, 1.3754, 1.3718, 1.3671, 1.3631, 1.3602, 1.3514, 1.3326)
                # ('1B', '1W', '1M', '3M', '6M', '9M', '12M', '2Y', '5Y'),  ## USD/CAD has spot_offset = '1B', hence '1B' forward conflicts with spot
                # (1.3773, 1.377, 1.3754, 1.3718, 1.3671, 1.3631, 1.3602, 1.3514, 1.3326)

            )
        },
    }
}

def run():
    DataCreator.create_mkt_data_with_timetag(fx_data, (RDate, 'tenor'))

if __name__ == '__main__':
    run()
