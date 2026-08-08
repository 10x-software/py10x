from xxfin.fx_spot_fwd_quotable import FXForwardQuotable, FXSpotQuotable
from xxfin.mkt_quotables_scope import TenorBasedQuotablesScope


class FxForwardCurveMas(TenorBasedQuotablesScope):
    s_data_per_market = {
        'GBP/USD':  {
            FXSpotQuotable:     '0C',   ## presence of the class matters, value is irrelevant
            FXForwardQuotable:  '1B, 1W, 1M, 3M, 6M, 9M, 12M, 2Y, 5Y, 20Y'
        },
        'EUR/USD':  {
            FXSpotQuotable:     '0C',   ## presence of the class matters, value is irrelevant
            FXForwardQuotable:  '1B, 1W, 1M, 3M, 6M, 9M, 12M, 2Y, 5Y, 10Y'
        },
        'USD/CHF': {
            FXSpotQuotable:     '0C',  ## presence of the class matters, value is irrelevant
            FXForwardQuotable:  '1B, 1W, 1M, 3M, 6M, 9M, 12M, 2Y, 5Y'
        },
        'USD/CAD': {
            FXSpotQuotable:     '0C',  ## presence of the class matters, value is irrelevant
            FXForwardQuotable:  '1W, 1M, 3M, 6M, 9M, 12M, 2Y, 5Y'   ## Note: USD/CAD has spot_offset = '1B', hence '1B' forward would conflict with spot
        },
        'USD/JPY': {
            FXSpotQuotable:     '0C',  ## presence of the class matters, value is irrelevant
            FXForwardQuotable:  '1B, 1W, 1M, 3M, 6M, 9M, 12M, 2Y, 5Y, 10Y'
        },
    }

