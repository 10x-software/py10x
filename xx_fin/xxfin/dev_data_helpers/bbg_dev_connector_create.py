from decimal import Decimal

from core_10x.trait_filter import f

from xxfin.bbg_adaptors.bbg_adaptor import BbgAdaptorIR
from xxfin.bbg_adaptors.bbg_connector import DevBbgConnector, LiveBbgConnector
from xxfin.dev_data_helpers.data_creator import DataCreator
from xxfin.mkt_adaptor import MktDataAdaptor
from xxfin.mkt_quotables_scope import MktQuotablesScope
from xxfin.pricing_context import PricingContext


def run():
    records = {}
    for mqs in MktQuotablesScope.load_many():
        for pc in PricingContext.load_many(f(mkt_data_provider_name='XX_DEV')):
            for quotable_class, stub in mqs.quotable_class_and_stubs_generator(pc.md_date):
                dev_q = quotable_class.existing_instance(mkt_name=mqs.mkt_name, **stub, **pc.md_basis, _throw=False)
                if dev_q:
                    adaptor_cls = MktDataAdaptor.adaptor(quotable_class, provider_name='BBG')
                    ticker = adaptor_cls.ticker(dev_q)
                    px_last = float(Decimal(str(dev_q.quote)) * 100) if issubclass(adaptor_cls, BbgAdaptorIR) else dev_q.quote
                    records[(ticker, pc.md_date)] = px_last

    DataCreator.create(DevBbgConnector, ({ 'provider_name': 'BBG_DEV', 'records': records },))
    DataCreator.create(LiveBbgConnector, ({ 'provider_name': 'BBG' },))

if __name__ == '__main__':
    run()
