from core_10x.traitable import Traitable, T, RC, RC_TRUE

class Person(Traitable):
    first_name: str     = T(T.ID)
    last_name: str      = T(T.ID)

    age: int            = T(1)
    full_name: str      = T(T.EXPENSIVE)

    older_than: bool    = T()

    def full_name_get(self) -> str:
        return f'{self.first_name} {self.last_name}'

    def full_name_set(self, trait, value: str) -> RC:
        parts = value.split(' ')
        if(len(parts) != 2):
            return RC(False, f'"{value}" - must be "first_name last_name"')

        self.first_name = parts[0]
        self.last_name = parts[1]
        return RC_TRUE

    def older_than_get(self, age: int) -> bool:
        return self.age > age