import random

from xxcommon.rdate import BIZDAY_ROLL_RULE, RDate

from xxfin.dev_data_helpers.data_creator import DataCreator
from xxfin.fin_calendar import FinCalendar

if __name__ == '__main__':

    from core_10x.exec_control import CACHE_ONLY, CONVERT_VALUES_ON, GRAPH_ON

    from xxfin.ccy_cross import Ccy, CcyCross

    fake_ccy_header = dict(
        bank_calendar           =FinCalendar.existing_instance(name='FD'),

        settle_offset           = RDate('2B'),  ## default
        spot_offset             = RDate('2B'),  ## default
        roll_rule               =BIZDAY_ROLL_RULE.FOLLOWING,  ## default

        is_deliverable          =True,  ## default
        discounting_mkt_name    ='SOFR',
    )
    ccy_lists = dict(
        _major_ccys         = (
            'EUR', 'GBP', 'AUD', 'NZD',
            'USD',   ## we deal with dollar crosses separately, but can leave it here. no harm
            'CAD', 'CHF', 'JPY'
        ),

        _nordics            = ('SEK', 'NOK', 'DKK'),
        _dev_asia           = ('SGD', 'HKD'),
        _pegged_ME          = ('SAR', 'AED'),     ## normally not used outside retail (USD instead bcz of peg)
        _large_asia         = ('KRW', 'CNH', 'CNY', 'TWD', 'THB'),   ## shouldn't allow CNH/CNY
        _other_EM_good_liq  = ('ZAR', 'TRY', 'PLN', 'HUF', 'CZK', 'MXN', 'BRL', 'CLP', 'COP'),
        _other_EM_less_liq  = ('RUB', 'INR', 'IDR', 'MYR', 'PHP', 'PEN', 'ILS', 'SAR', 'ARS'),    ## SAR, AED are low due to peg; ILS maybe higher
    )
    ccys = []
    for ccyl in ccy_lists.values():
        ccys += list(ccyl)

    data = tuple([ dict(name = ccy_name, **fake_ccy_header) for ccy_name in ccys])

    DataCreator.create(Ccy, data, save = False)

    cross = 'GBP/EUR'
    with CONVERT_VALUES_ON():
        #c1 = CcyCross(cross = cross)
        c = CcyCross(base_ccy = 'GBP', quote_ccy = 'EUR')
        #r = CcyCross.resolve(cross = cross)

        rr = CcyCross.resolve('GBP/GBP')

        random.shuffle(ccys)

        for ccy1 in ccys:
            for ccy2 in reversed(ccys):
                print( f'normal cross for the ccy pair ({ccy1}, {ccy2}) is {CcyCross.normal_cross(ccy1,ccy2)}')
