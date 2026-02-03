from core_10x.traitable_heir import TraitableHeir, T, RT

class Conventions(TraitableHeir):
    mkt_name: str   = T(T.ID)

    days_to_settle: int = T()

c_dir = dict(Conventions.s_dir)

class XConventions(Conventions):
    days_to_settle_twice: int   = RT()

    def days_to_settle_twice_get(self):
        return 2*self.days_to_settle

c_dir2 = Conventions.s_dir

if __name__ == '__main__':
    from core_10x.manual_tests.traitable_heir_test import Conventions, XConventions

    mkt_name = 'WTI NYMEX'
    c = Conventions(mkt_name = mkt_name)
    c.days_to_settle = 2
    print(c.days_to_settle)

    loc = 'ICE'
    mkt_name2 = f'{mkt_name} {loc}'
    c2 = Conventions(mkt_name = mkt_name2)
    c2._grantor = c

    print(c2.days_to_settle)

    c.days_to_settle = 3
    print(c2.days_to_settle)

    xc = XConventions(mkt_name = mkt_name)
    xc._grantor = c

    print(xc.days_to_settle_twice)