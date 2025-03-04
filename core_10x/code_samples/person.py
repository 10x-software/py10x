from core_10x.named_constant import NamedConstant
from core_10x.trait_definition import RT
from core_10x.traitable import Traitable, T, RC, RC_TRUE

class WEIGHT_QU( NamedConstant ):
    LB =    ( 'lb',     1. )
    KG =    ( 'kg',     2.205 )
    G =     ( 'g',      0.002205 )
    CT =    ( 'ct',     0.0004409 )

class Person(Traitable):
    first_name: str         = T(T.ID)
    last_name: str          = T(T.ID)

    age: int                = T(1)
    full_name: str          = T(T.EXPENSIVE)
    weight_lbs: float       = T()
    weight: float           = T()
    weight_qu: WEIGHT_QU    = T(default = WEIGHT_QU.LB)

    older_than: bool        = RT()


    def full_name_get(self) -> str:
        return f'{self.first_name} {self.last_name}'

    def full_name_style_sheet(self):
        age = self.age
        return T.fg_color('red' if age < 20 or age > 70 else 'green')

    def full_name_set(self, trait, value: str) -> RC:
        parts = value.split(' ')
        if(len(parts) != 2):
            return RC(False, f'"{value}" - must be "first_name last_name"')

        self.first_name = parts[0]
        self.last_name = parts[1]
        return RC_TRUE

    def older_than_get(self, age: int) -> bool:
        return self.age > age

    #-- getter and setter for weight trait
    def weight_get( self ) -> float:
        return self.weight_lbs / self.weight_qu.value

    def weight_set( self, trait: T, value ) -> RC:  # -- trait setter gets its trait and the value and must return RC
        value = trait.from_any( value )
        return self.set_value( self.trait('weight_lbs'), value * self.weight_qu.value) #TODO: set_values(**dict) to set multiple values at once