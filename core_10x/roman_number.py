from core_10x.named_constant import Enum, NamedConstantTable


# ruff: noqa: E741
class R:
    class Symbol(Enum):
        I = () 
        V = ()
        X = ()
        L = ()
        C = ()
        D = ()
        M = ()

    class Attr(Enum):
        VALUE           = ()
        REPEAT          = ()
        SUBTRACTABLE    = ()

    SYMBOL_TABLE = NamedConstantTable(Symbol, Attr,
        #       VALUE       REPEAT      SUBTRACTABLE
        I = (   1,          3,          True ),
        V = (   5,          1,          False ),
        X = (   10,         3,          True ),
        L = (   50,         1,          False ),
        C = (   100,        3,          True ),
        D = (   500,        1,          False ),
        M = (   1000,       3,          True ),
    )

    def __init__(self, text: str):
        text = text.upper()
        x = 0
        prev_values = [0, 0, 0]
        for i, symbol in enumerate(reversed(text)):
            ref = R.SYMBOL_TABLE[symbol]
            v = ref.VALUE

            #-- Rules
            repeat = ref.REPEAT
            over_repeated = all(v == prev_values[i] for i in range(repeat))
            assert not over_repeated, f"'{symbol}' is repeated more than {repeat} times"

            subtractable = ref.SUBTRACTABLE
            if not subtractable and v < prev_values[0]:
                raise AssertionError(f"'{symbol}' may not occur before '{text[ -i ]}'")

            if v >= prev_values[0]:
                x += v
            else:
                x -= v

            prev_values[2] = prev_values[1]
            prev_values[1] = prev_values[0]
            prev_values[0] = v

        self.roman = text
        self.value = x

    def __repr__(self):
        return f'{self.roman} = {self.value}'

if __name__ == '__main__':
    x = R('IX')
    y = R('MCMLXXXIV')
