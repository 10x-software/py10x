from datetime import date

from core_10x.named_constant import NamedConstant
from core_10x.traitable import Traitable, T, RT, Ui, RC, RC_TRUE

class WEIGHT_QU( NamedConstant ):
    LB =    ( 'lb',     1. )
    KG =    ( 'kg',     2.205 )
    G =     ( 'g',      0.002205 )
    CT =    ( 'ct',     0.0004409 )

class Person(Traitable):
    first_name: str         = T(T.ID)
    last_name: str          = T(T.ID)
    dob: date               = T()
    weight_lbs: float       = T(fmt = ',.4f')

    age: int                = RT()
    full_name: str          = RT(T.EXPENSIVE)
    weight: float           = RT()
    weight_qu: WEIGHT_QU    = RT(default = WEIGHT_QU.LB)

    older_than: bool        = RT()


    def dob_set(self, trait, value: date) -> RC:
        today = date.today()
        if value > today:
            return RC(False, f'{value} may not be after {today}')
        return self.raw_set_value(trait, value)

    def full_name_get(self) -> str:
        return f'{self.first_name} {self.last_name}'

    def full_name_style_sheet(self) -> dict:
        age = self.age
        return {Ui.FG_COLOR: 'red' if age < 20 or age > 70 else 'green'}

    def full_name_set(self, trait, value: str) -> RC:
        parts = value.split(' ')
        if(len(parts) != 2):
            return RC(False, f'"{value}" - must be "first_name last_name"')

        self.first_name = parts[0]
        self.last_name = parts[1]
        return RC_TRUE

    def age_get(self) -> int:
        dob = self.dob
        if not dob:
            return 0

        today = date.today()
        years = today.year - dob.year
        dm = today.month - dob.month
        if dm < 0:
            return years - 1

        if dm > 0:
            return years

        return years - 1 if today.day < dob.day else years

    def older_than_get(self, age: int) -> bool:
        return self.age > age

    #-- getter and setter for weight trait
    def weight_get(self) -> float:
        return self.weight_lbs / self.weight_qu.value

    def weight_set(self, trait, value) -> RC:  #-- trait setter gets its trait and the value and must return RC
        return self.set_values( weight_lbs = value * self.weight_qu.value)

    def weight_to_str(self, trait, value) -> str:
        return f'{trait.to_str(value)} {self.weight_qu.label}'

    def to_str(self) -> str:
        return self.full_name