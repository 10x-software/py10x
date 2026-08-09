from datetime import date

from xxfin.dev_data_helpers.data_creator import DataCreator
from xxfin.pricing_context import PRICING_MODE, PricingContext
from xxfin.snapshot import SNAPSHOT

data = (
    dict(
        name                    = 'Abu Dhabi 20250530',
        pricing_mode            = PRICING_MODE.PRICING,
        mkt_data_provider_name  = 'XX_DEV',
        snapshot                = SNAPSHOT.CLOSE,
        md_date                 = date(2025, 5, 30)
    ),
    dict(
        name                    = 'Abu Dhabi 20251010',
        pricing_mode            = PRICING_MODE.PRICING,
        mkt_data_provider_name  = 'XX_DEV',
        snapshot                = SNAPSHOT.CLOSE,
        md_date                 = date(2025, 10, 10)
    ),
)

def run():
    DataCreator.create(PricingContext, data)

if __name__ == '__main__':
    run()

