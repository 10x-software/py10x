from xxcommon.rdate import TENOR_FREQUENCY

from xxfin.bbg_adaptors.bbg_adaptor import BbgAdaptorIR
from xxfin.ir_cash_deposit_quotable import IRCashDepositQuotable


class IRCashDepositQuotableBbgAdaptor(BbgAdaptorIR):
    BBG_INDEX = {
        'SOFR': 'SOFRRATE Index',
        'SONIA': 'SONIO/N Index',
        'ESTR': 'ESTRON Index',
        'SARON': 'SARON Index',
        'TONA': 'MUTKCALM Index',
        'CORRA': 'CAONREPO Index',
    }
    BBG_CUT = {'SARON': 'L'}

    @classmethod
    def ticker(cls, quotable: IRCashDepositQuotable) -> str:
        tenor = quotable.tenor
        mkt_name = quotable.mkt_name
        if tenor.freq == TENOR_FREQUENCY.BIZDAY:
            assert tenor.count == 1
            return cls.BBG_INDEX[mkt_name]

        if tenor.freq == TENOR_FREQUENCY.WEEK:
            assert tenor.count == 1
            bbg_tenor = '1Z'
        elif tenor.freq == TENOR_FREQUENCY.MONTH:
            assert 1 <= tenor.count <= 12
            bbg_tenor = chr(ord('A') + tenor.count - 1) if tenor.count < 12 else '1'
        else:
            assert False, tenor.freq

        return f'{cls.BBG_MKT[mkt_name]}{bbg_tenor} BGN{cls.BBG_CUT.get(mkt_name, "")}{cls.SUFFIX}'
