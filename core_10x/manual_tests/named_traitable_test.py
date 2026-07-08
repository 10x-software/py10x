from datetime import date
from core_10x.traitable import NamedTraitable, RT
from core_10x.exec_control import CACHE_ONLY

class Cal(NamedTraitable):
    holidays: list  = RT()

class Ccy(NamedTraitable):
    bank_cal: Cal   = RT()

if __name__ == '__main__':
    with CACHE_ONLY():
        ukc = Cal(name = 'UK', holidays = [date(2026, 1, 1), date(2026, 1, 2)], _update = True)
        gbp = Ccy(name = 'GBP', bank_cal = ukc, _update = True)

        gbp2 = Ccy.existing_instance(name = 'GBP')
        gbp3 = Ccy('GBP')
        assert gbp2 == gbp3