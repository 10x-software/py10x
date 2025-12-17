from core_10x.traitable import RC, RC_TRUE, RT, T, Traitable


class Cross(Traitable):
    cross: str              = RT(T.ID)  // 'e.g., GBP/USD or CHF/JPY'

    base_ccy: str           = RT()      // 'Base (left) currency'
    quote_ccy: str          = RT()      // 'Quote (right) currency'

    def cross_get(self) -> str:
        return f'{self.base_ccy}/{self.quote_ccy}'

    def cross_set(self, trait, cross: str) -> RC:
        parts = cross.split('/')
        assert len(parts) == 2
        c1, c2 = parts
        rc1 = self.set_value('base_ccy', c1)
        rc2 = self.set_value('quote_ccy', c2)
        if rc1 and rc2:
            return RC_TRUE
        rc = RC(True)
        rc <<= rc1
        rc <<= rc2
        return rc

if __name__ == '__main__':
    cross = 'A/B'

    #-- Case 1 - doesn't allow to create the second instance claiming it sets non-ID traits
    c1 = Cross(cross = cross)
    try:
        c2 = Cross(cross = cross)
    except Exception as e:
        print(e)

    #-- Case 2 - update is "working" exactly as the ctor
    try:
        c3 = Cross.update(cross = cross)
    except Exception as e:
        print(e)

    #-- Case 3: update complains about not setting at least one ID-trait - WRONG!
    try:
        c4 = Cross.update(base_ccy = 'A', quote_ccy = 'B')
    except Exception as e:
        print(e)

