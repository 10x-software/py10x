from xxfin.ir_cash_deposit_quotable import IRCashDepositQuotable
from xxfin.ir_swap_quotable import IRSwapQuotable
from xxfin.mkt_quotables_scope import TenorBasedQuotablesScope


class IRZeroRateCurveMas(TenorBasedQuotablesScope):
    s_data_per_market = dict(
        SOFR = {
            IRCashDepositQuotable:  '1B, 1W, 1M, 3M, 6M, 9M, 12M',
            # IRCashDepositQuotable: '1B, 1W, 1M, 3M, 6M, 9M',  # -- root solver has a problem with 12M :-)
            IRSwapQuotable: '5Y, 10Y, 20Y, 30Y'
        },
        SONIA = {
            IRCashDepositQuotable: '1B, 1W, 1M, 3M, 6M, 9M, 12M',
            IRSwapQuotable: '5Y, 10Y, 20Y, 30Y'
        },
        TONA = {
            IRCashDepositQuotable:  '1B, 1W, 1M, 3M, 6M, 9M, 12M',
            IRSwapQuotable:         '5Y, 10Y, 15Y, 20Y, 30Y'
        },
        CORRA = {
            IRCashDepositQuotable:  '1B, 1W, 1M, 3M, 6M, 9M, 12M',
            IRSwapQuotable:         '5Y, 10Y, 20Y, 30Y'
        },
        SARON = {
            IRCashDepositQuotable:  '1B, 1W, 1M, 3M, 6M, 12M',
            IRSwapQuotable:         '5Y, 10Y, 20Y, 30Y'
        },
        ESTR = {
            IRCashDepositQuotable:  '1B, 1W, 1M, 3M, 6M, 12M',
            IRSwapQuotable:         '5Y, 10Y, 20Y, 30Y'
        },
    )
