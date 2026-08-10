from xxcommon.rdate import TENOR_FREQUENCY

from xxfin.bbg_adaptors.bbg_adaptor import BbgAdaptorFX
from xxfin.fx_spot_fwd_quotable import FXForwardQuotable, FXSpotQuotable


class FXSpotQuotableBbgAdaptor(BbgAdaptorFX):
    @classmethod
    def ticker(cls, quotable: FXSpotQuotable) -> str:
        return f'{cls.BBG_MKT[quotable.mkt_name]}{cls.SUFFIX}'


class FXForwardQuotableBbgAdaptor(BbgAdaptorFX):
    @classmethod
    def ticker(cls, quotable: FXForwardQuotable) -> str:
        tenor = quotable.tenor
        if tenor.freq == TENOR_FREQUENCY.BIZDAY:
            if tenor.count == 1:
                tenor = 'ON'
            if tenor.count == 2:  # TODO: if RDate.same_values(tenor,mkt_conventions.spot_offset):
                tenor = 'SN'
        return f'{cls.BBG_MKT[quotable.mkt_name]}{tenor}{cls.SUFFIX}'
