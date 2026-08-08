from xxcommon.rdate import TENOR_FREQUENCY

from xxfin.bbg_adaptors.bbg_adaptor import BbgAdaptorIR
from xxfin.ir_swap_quotable import IRSwapQuotable


class IRSwapQuotableBbgAdaptor(BbgAdaptorIR):
    @classmethod
    def ticker(cls, quotable: IRSwapQuotable) -> str:
        tenor = quotable.tenor
        assert tenor.freq == TENOR_FREQUENCY.YEAR
        return f'{cls.BBG_MKT[quotable.mkt_name]}{tenor.count}{cls.SUFFIX}'
