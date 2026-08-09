from datetime import date

from xxcommon.rdate import RDate

from xxfin.dev_data_helpers.data_creator import DataCreator
from xxfin.ir_zero_rate_curve import IRCashDepositQuotable, IRSwapQuotable

zrc_data = {
    date(2025, 3, 12): dict(
        SOFR = {
            IRCashDepositQuotable: (
                ('1B',  '1W',   '1M',   '3M',   '6M',   '9M',   '12M'),
                (.03,   .03,    .03,    .03,    .03,    .03,    .03),
            ),
            IRSwapQuotable: (
                ('5Y',  '10Y',  '20Y',  '30Y'),
                (.03,   .03,    .03,    .03),
            )
        },
        SONIA = {
            IRCashDepositQuotable: (
                ('1B',  '1W',   '1M',   '3M',   '6M',   '9M',   '12M'),
                (.03,   .0302,  .03166, .0325,  .035,   .0375,  .04),
            ),
            IRSwapQuotable: (
                ('5Y',  '10Y',  '20Y',  '30Y'),
                (.055,  .08,    .105,   .155),
            )
        },
    ),
    date(2025, 5, 30): dict(
        SOFR = {
            IRCashDepositQuotable: (
                ('1B', '1W', '1M', '3M', '6M', '9M', '12M'),
                (.04, .04, .04, .04, .04, .04, .04),
            ),
            IRSwapQuotable: (
                ('5Y', '10Y', '20Y', '30Y'),
                (.04, .04, .04, .04),
            )
        },
        SONIA = {
            IRCashDepositQuotable: (
                ('1B', '1W', '1M', '3M', '6M', '9M', '12M'),
                (.03, .0302, .03166, .0325, .035, .0375, .04),
            ),
            IRSwapQuotable: (
                ('5Y', '10Y', '20Y', '30Y'),
                (.055, .08, .105, .155),
            )
        },
    ),
    date(2025, 7, 3): dict(     ## Thursday before 4th of July
        SOFR={  ## linear from 1B 3% to 30Y 13%
            IRCashDepositQuotable: (
                ('1B',  '1W',       '1M',       '3M',       '6M',       '9M',       '12M'),
                (.03,   .030055,    .030269,    .030824,    .031658,    .032491,    .033325),
            ),
            IRSwapQuotable: (
                ('5Y',      '10Y',      '20Y',      '30Y'),
                (.046659,   .063327,    .096664,    .13),
            )
        },
        SONIA={     ## linear from 1B -1% to 30Y 20%
            IRCashDepositQuotable: (
                ('1B',  '1W',       '1M',       '3M',       '6M',       '9M',       '12M'),
                (-0.01, -.009889,   -.009454,   -.008325,   -.006631,   -.004937,   -.003244),
            ),
            IRSwapQuotable: (
                ('5Y',      '10Y',      '15Y',      '20Y',      '25Y',      '30Y'),
                (.023855,   0.057729,   0.091603,   0.125477,   0.159351,   0.2),
            )
        },
    ),
    date(2025, 10, 10): dict(   ## Friday before Columbus Day
        SOFR={  ## linear from 1B 1% to 30Y 6%
            IRCashDepositQuotable: (
                ('1B', '1W',    '1M',   '3M',       '6M',       '9M',       '12M'),
                (.01, .010027,  .01013, .010399,    .010802,    .011205,    .011609),
            ),
            IRSwapQuotable: (
                ('5Y',      '10Y',      '20Y',      '30Y'),
                (.012061,   .01216,    .012256,    .01246),     ## less steep yet
                # (.018061,   .020126,    .022256,    .0246),   ## less steep
                # (.018061,   .026126,    .042256,    .06),     ## ORIGINAL << maybe too steep
            )
        },
        SONIA={  ## linear from 1B -0.5% to 30Y 4%
            IRCashDepositQuotable: (
                ('1B',      '1W',       '1M',       '3M',       '6M',       '9M',       '12M'),
                (-0.005,    -.004976,   -.004883,   -.004641,   -.004278,   -.003915,   -.003552),
            ),
            IRSwapQuotable: (
                ('5Y',      '10Y',      '15Y',      '20Y',      '25Y',      '30Y'),
                (.002255,   0.009513,   0.016772,   0.024031,   0.03129,    0.04),
            )
        },
        TONA = {
            IRCashDepositQuotable: (
                ('1B',      '1W',       '1M',   '3M',   '6M',       '9M',       '12M'),
                (0.00727,   0.0073,     0.0074, 0.0076, 0.0082,     0.0088,     0.0095),
            ),
            IRSwapQuotable: (
                ('5Y',      '10Y',      '15Y',   '20Y',     '30Y'),
                (.0125,     0.015,      0.016,   0.0165,    0.0165),
            )
        },
        CORRA = {
            IRCashDepositQuotable: (
                ('1B',   '1W',      '1M',    '3M',   '6M',    '9M',     '12M'),
                (0.0229, 0.02285,   0.02262, 0.0226, 0.02265, 0.0228,   0.0231),
            ),
            IRSwapQuotable: (
                ('5Y',  '10Y',  '20Y',  '30Y'),
                (.0296, 0.0341, 0.0358, 0.0385),
            )
        },

    ),
    date(2025, 5, 22): dict(  ## Thursday before Memorial Day on Monday 5/26/25
        SOFR={  ## a hump: linear from 1B 2% to 5Y 5% to 30Y 3%
            IRCashDepositQuotable: (
                ('1B', '1W',    '1M',       '3M',       '6M',       '9M',       '12M'),
                (.02, .020099,  .020484,    .021484,    .022985,    .024486,    .025987),
            ),
            IRSwapQuotable: (
                ('5Y',  '10Y',      '20Y',      '30Y'),
                (.05,   .046154,    .038462,    .03),
            )
        },
        SONIA={  ## linear downward from 1B 5% to 30Y 3%
            IRCashDepositQuotable: (
                ('1B',  '1W',       '1M',       '3M',   '6M',       '9M',       '12M'),
                (.05,   .049989,    .049948,    .04984, .049679,    .049518,    .049357),
            ),
            IRSwapQuotable: (
                ('5Y',      '10Y',  '15Y',      '20Y',      '25Y',      '30Y'),
                (.046776,   .04355, .040323,    .037097,    .033871,    .03),
            )
        },
    ),

}

def run():
    DataCreator.create_mkt_data_with_timetag(zrc_data, (RDate, 'tenor'))

if __name__ == '__main__':
    run()
