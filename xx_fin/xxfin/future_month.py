from datetime import date

from xxcommon.rdate import BIZDAY_ROLL_RULE, RDate

from xxfin.fin_calendar import FinCalendar


class FutureMonth:
    SYMBOLS                             = 'FGHJKMNQUVXZ'
    BEGINNING_OF_TIME                   = 1960
    TWO_DIGIT_YEAR_CUTOFF_TO_21_CENTURY = 60

    ## TODO: 1-digit year for "near" years (e.g., 'G9' for Feb2029) is officially legit,
    ##      but the conversion to a full 4-digit year depends on the PricingContext.md_date ( in 2026 G9 = G29, but in 2030 it = G39) << BAD!
    @classmethod
    def to_date(cls, contract: str) -> date:
        ## allowed form G26 or G2026 for February 2026 contract
        n = len(contract)
        if n not in (3, 5):
            raise AssertionError(f'Future {contract} should be of format <contract month symbol><year> with 2- or 4-digit year')

        ctr_letter = contract[0].upper()
        month_index = cls.SYMBOLS.find(ctr_letter)
        if month_index == -1:
            raise AssertionError(f'Contract month {ctr_letter} of {contract} must be one of the standard future contract months: {cls.SYMBOLS}')

        try:
            year = int(contract[1:])
        except Exception as e:
            raise AssertionError(f'Invalid contract year {contract[1:]} in {contract}') from e

        if n == 5:
            if year <= cls.BEGINNING_OF_TIME:
                raise AssertionError(f'Contract year of {contract} must be greater than {cls.BEGINNING_OF_TIME}')

        else:   #-- n == 2, y < 100
            ## NOTE: 1-digit year is not allowed yet
            year = year + 2000 if year < cls.TWO_DIGIT_YEAR_CUTOFF_TO_21_CENTURY else year + 1900

        return date(year, month_index+1, 1)

    @classmethod
    def date_to_fut_month(cls, d: date, two_digit_year:bool = False) -> str:
        return f'{cls.SYMBOLS[d.month-1]}{d.year if not two_digit_year else str(d.year)[2:]}'
        # return f'{cls.__class__.SYMBOLS[d.month-1]}{d.year if not two_digit_year else str(d.year)[2:]}'

    @classmethod
    def next_fut_month(cls, contract: str, next_num: int = 1) -> str:
        if not next_num:
            return contract
        d0 = FutureMonth.to_date(contract)
        d1 = RDate(f'{next_num}M').apply(d0, FinCalendar.none(), BIZDAY_ROLL_RULE.NO_ROLL)
        return FutureMonth.date_to_fut_month(d1)

    @classmethod
    def number_of_next_fut_months(cls, contract: str, last_month_num: int, first_month_num: int = 1) -> list:
        if not last_month_num and not first_month_num:
            return [contract.upper()]
        d0 = FutureMonth.to_date(contract)
        return [FutureMonth.date_to_fut_month(RDate(f'{i}M').apply(d0, FinCalendar.none(), BIZDAY_ROLL_RULE.NO_ROLL)) for i in range(first_month_num, last_month_num+1)]

    @classmethod
    def full_name(cls, contract: str) -> str:
        return cls.date_to_fut_month(cls.to_date(contract), two_digit_year = False)

    def __init__(self, contract: str):
        self.fdate = self.__class__.to_date(contract)

    def __repr__(self):     # pragma: no cover
        d = self.fdate
        return f'{self.__class__.SYMBOLS[d.month-1]}{d.year}'

    def __eq__(self, other):
        return self.fdate == other.fdate

    def __ne__(self, other):
        return self.fdate != other.fdate

    def __le__(self, other):
        return self.fdate <= other.fdate

    def __ge__(self, other):
        return self.fdate >= other.fdate

    def __gt__(self, other):
        return self.fdate > other.fdate

    def __lt__(self, other):
        return self.fdate < other.fdate
