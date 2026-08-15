from __future__ import annotations

from core_10x.global_cache import cache
from core_10x.named_constant import NamedConstant
from core_10x.traitable import RC, RC_TRUE, RT, T, Traitable

from xxfin.ccy import Ccy, FinCalendar


class CCY_CROSS_TYPE(NamedConstant):
    NONE        = 0
    NORMAL      = 1
    INVERTED    = -1
    # REPLICATED - is not needed here, as resolve() will return a pair of contexts

class CcyCross(Traitable):
    """
    Today, USD is the world reserve ccy. Many rules, quotable markets, etc. are fully based on this fact.
    If that changes, the below code MAY need to be revisited!
    """
    @staticmethod
    @cache
    def amer_exceptions() -> set:
        exceptions = ( 'GBP', 'EUR', 'AUD', 'NZD' )
        return { Ccy.verified(name) for name in exceptions }

    cross: str              = RT(T.ID)          // 'e.g., GBP/USD or CHF/JPY'
    base_ccy: Ccy           = RT(T.ID_LIKE)     // 'Base (left) currency'
    quote_ccy: Ccy          = RT(T.ID_LIKE)     // 'Quote (right) currency'

    is_deliverable: bool    = RT()              // 'Deliverable cross settles physically for both sides'
    delivery_ccy: Ccy       = RT()              // 'Delivery currency for a NON-deliverable cross'
    calendar: FinCalendar   = RT()

    @classmethod
    def to_currencies(cls, cross: str) -> tuple:
        parts = cross.split('/')
        assert len(parts) == 2, f"Invalid cross '{cross}'"
        return (Ccy.verified(parts[0]), Ccy.verified(parts[1]))

    @classmethod
    def from_currencies(cls, base_ccy, quote_ccy) -> str:
        base_ccy, quote_ccy = cls.currencies(base_ccy = base_ccy, quote_ccy = quote_ccy)
        return f'{base_ccy.name}/{quote_ccy.name}'

    @classmethod
    def currencies(cls, cross = '', base_ccy = None, quote_ccy = None) -> tuple:
        if cross:
            return cls.to_currencies(cross)

        return (Ccy.verified(base_ccy), Ccy.verified(quote_ccy))

    @classmethod
    def verify(cls, cross = '', base_ccy = None, quote_ccy = None) -> RC:
        try:
            cls.currencies(cross=cross, base_ccy=base_ccy, quote_ccy=quote_ccy)
            return RC_TRUE
        except Exception as e:
            return RC(False, str(e))

    def cross_get(self) -> str:
        return self.from_currencies(self.base_ccy, self.quote_ccy)

    def cross_set(self, trait, cross: str) -> RC:
        ccy1, ccy2 = self.to_currencies(cross)
        rc1 = self.set_value('base_ccy', ccy1)
        rc2 = self.set_value('quote_ccy', ccy2)
        if rc1 and rc2:
            return RC_TRUE
        rc = RC(True)
        rc <<= rc1
        rc <<= rc2
        return rc

    def is_deliverable_get(self) -> bool:
        base_deliverable = self.base_ccy.is_deliverable
        quote_deliverable = self.quote_ccy.is_deliverable
        return base_deliverable and quote_deliverable

    def delivery_ccy_get(self) -> Ccy:
        if self.is_deliverable:
            return None
        if self.quote_ccy.is_deliverable:
            return self.quote_ccy
        elif self.base_ccy.is_deliverable:
            return self.base_ccy
        else:
            return None

    def calendar_get(self) -> FinCalendar:
        at_most_three_calendars = {self.quote_ccy.bank_calendar, self.base_ccy.bank_calendar, Ccy.USD().bank_calendar}
        return FinCalendar.union(*at_most_three_calendars)

    @classmethod
    def is_same_ccy_cross(cls, cross: str) -> bool:
        ccys = cross.split('/')
        if len(ccys) != 2:
            return False
        return ccys[0] == ccys[1]

    @classmethod
    def invert_cross(cls, cross: str) -> str:
        ccy1, ccy2 = cls.currencies(cross = cross)
        return cls.from_currencies(ccy2, ccy1)

    @classmethod
    def is_dollar_cross(cls, ccy1, ccy2) -> bool:
        ccy1, ccy2 = cls.currencies(base_ccy = ccy1, quote_ccy = ccy2)
        return ccy1 == Ccy.USD() or ccy2 == Ccy.USD()

    @classmethod
    def dollar_cross(cls, ccy) -> CcyCross:
        dcp = cls.dollar_cross_pair(ccy, Ccy.USD())
        return dcp[0] if dcp else None  #-- if ccy is USD

    @classmethod
    def dollar_cross_pair(cls, ccy1, ccy2) -> tuple:
        resolve_info = cls.resolve(base_ccy = ccy1, quote_ccy = ccy2)
        return tuple(nc for nc in resolve_info[1: :2 ] if nc)

    @classmethod
    def resolve(cls, cross = '', base_ccy = None, quote_ccy = None) -> tuple:   #-- (cross_type1, mc1, cross_type2, mc2)
        base_ccy, quote_ccy = cls.currencies(cross = cross, base_ccy = base_ccy, quote_ccy = quote_ccy)
        return cls._resolve(base_ccy, quote_ccy)

    @classmethod
    @cache
    def _resolve(cls, base_ccy: Ccy, quote_ccy: Ccy) -> tuple:
        """
        All cases:
        cross_type: Normal = 1, inverted = -1 (none = 0):
        for a non-$ cross, 1st number is for base $-cross, 2nd - for quote
                        base:
                        | Exc   | non-Exc   | USD
                --------|-------|-----------|-------
        quote:  Exc     | 1,-1  | -1,-1     | -1, 0
                no-Exc  | 1, 1  | -1, 1     |  1, 0
                USD     | 1, 0  | -1, 0     |  0, 0

        All cases coverage by cases below:
                        base:
                        | Exc   | non-Exc   | USD
                --------|-------|-----------|--------
        quote:  Exc     | 1b    | 3b        | 2a
                no-Exc  | 1c    | 3c        | 2b
                USD     | 1a    | 3a        | 0
        """
        assert all((
            base_ccy,   isinstance(base_ccy, Ccy),
            quote_ccy,  isinstance(quote_ccy, Ccy)
        )), f'{base_ccy} and {quote_ccy} must be known currencies'

        #-- 0) Same ccy: A/A
        if base_ccy == quote_ccy:
            return (CCY_CROSS_TYPE.NONE, None, CCY_CROSS_TYPE.NONE, None)

        base_exc = base_ccy in cls.amer_exceptions()
        quote_exc = quote_ccy in cls.amer_exceptions()

        #-- 1) AMER EX / A
        if base_exc:
            if quote_ccy.is_usd:  #-- AMER EX / USD     ## 1(a)
                return (
                    CCY_CROSS_TYPE.NORMAL,    cls(base_ccy = base_ccy,   quote_ccy = Ccy.USD()),
                    CCY_CROSS_TYPE.NONE,      None
                )

            if quote_exc:   #-- AMER EX / AMER EX       ## 1(b)
                return (
                    CCY_CROSS_TYPE.NORMAL,    cls(base_ccy = base_ccy,   quote_ccy = Ccy.USD()),
                    CCY_CROSS_TYPE.INVERTED,  cls(base_ccy = quote_ccy,  quote_ccy = Ccy.USD())
                )

            #-- AMER EX / not AMER EX                    ## 1(c)
            return (
                CCY_CROSS_TYPE.NORMAL, cls(base_ccy = base_ccy,   quote_ccy = Ccy.USD()),
                CCY_CROSS_TYPE.NORMAL, cls(base_ccy = Ccy.USD(),  quote_ccy = quote_ccy)
            )

        #-- 2) USD / A
        if base_ccy.is_usd:
            if quote_exc:       #-- USD / AMER EX        ## 2(a)
                return (
                    CCY_CROSS_TYPE.INVERTED,  cls(base_ccy = quote_ccy, quote_ccy = Ccy.USD()),
                    CCY_CROSS_TYPE.NONE,      None
                )
            #-- USD / non AMER EX                        ## 2(b)
            return (
                CCY_CROSS_TYPE.NORMAL, cls(base_ccy = Ccy.USD(), quote_ccy = quote_ccy),
                CCY_CROSS_TYPE.NONE,   None
            )

        #-- 3) non USD / A
        if quote_ccy.is_usd:  #-- non USD / USD          ## 3(a)
            return (
                CCY_CROSS_TYPE.INVERTED,  cls(base_ccy = Ccy.USD(), quote_ccy = base_ccy),
                CCY_CROSS_TYPE.NONE,      None
            )

        if quote_exc:       #-- non USD / AMER EX       ## 3(b)
            return (
                CCY_CROSS_TYPE.INVERTED,  cls(base_ccy = quote_ccy,   quote_ccy = Ccy.USD()),
                CCY_CROSS_TYPE.INVERTED,  cls(base_ccy = Ccy.USD(),   quote_ccy = base_ccy)
            )

        #-- non USD / non USD                           ## 3(c)
        #-- fix: the two legs were swapped (base's own cross returned as usd_cross2, and vice versa)
        return (
            CCY_CROSS_TYPE.INVERTED,  cls(base_ccy = Ccy.USD(), quote_ccy = base_ccy),
            CCY_CROSS_TYPE.NORMAL,    cls(base_ccy = Ccy.USD(), quote_ccy = quote_ccy)
        )

    _major_ccys         = (
        'EUR', 'GBP', 'AUD', 'NZD',
        'USD',   ## we deal with dollar crosses separately, but can leave it here. no harm
        'CAD', 'CHF', 'JPY'
    )
    _nordics            = ('SEK', 'NOK', 'DKK')
    _dev_asia           = ('SGD', 'HKD')
    _pegged_ME          = ('SAR', 'AED')     ## normally not used outside retail (USD instead bcz of peg)
    _large_asia         = ('KRW', 'CNH', 'CNY', 'TWD', 'THB')   ## shouldn't allow CNH/CNY
    _other_EM_good_liq  = ('ZAR', 'TRY', 'PLN', 'HUF', 'CZK', 'MXN', 'BRL', 'CLP', 'COP')
    _other_EM_less_liq  = ('RUB', 'INR', 'IDR', 'MYR', 'PHP', 'PEN', 'ILS', 'SAR', 'ARS')    ## SAR, AED are low due to peg; ILS maybe higher

    _ccy_hierarchies = (
        _major_ccys,
        _nordics,
        _dev_asia,
        _pegged_ME,
        _large_asia,
        _other_EM_good_liq,
        _other_EM_less_liq,
    )

    @classmethod
    def normal_cross(cls, ccy1: str, ccy2: str) -> str:
        for hierarchy in cls._ccy_hierarchies:
            cross = cls.normal_cross_from_ccy_hierarchy(ccy1, ccy2, hierarchy)
            if cross is not None:
                return cross

        return None

    @classmethod
    def is_normal_cross(cls, cross: str) -> bool:
        ccy1, ccy2 = cls.currencies(cross = cross)
        normal_cross = cls.normal_cross(ccy1, ccy2)
        return cross == normal_cross

    @classmethod
    def normal_cross_from_major_ccys_hierarchy(cls, ccy1: str, ccy2: str) -> str:
        return cls.normal_cross_from_ccy_hierarchy(ccy1, ccy2, cls._major_ccys)

    @classmethod
    def normal_cross_from_ccy_hierarchy(cls, ccy1: str, ccy2: str, ccy_hierarchy: tuple) -> str:
        if ccy1 == ccy2:
            return cls.from_currencies(ccy1, ccy2)

        try:
            index1 = ccy_hierarchy.index(ccy1)
        except Exception:
            index1 = None
        try:
            index2 = ccy_hierarchy.index(ccy2)
        except Exception:
            index2 = None

        if index1 is not None:
            if index2 is not None:
                return cls.from_currencies(ccy_hierarchy[min(index1, index2)], ccy_hierarchy[max(index1, index2)])
            return cls.from_currencies(ccy_hierarchy[index1], ccy2)

        return cls.from_currencies(ccy_hierarchy[index2], ccy1) if index2 is not None else None
