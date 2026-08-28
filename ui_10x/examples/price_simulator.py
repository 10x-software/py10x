import random
import threading
import yfinance as yf

from core_10x.traitable import RC, RT, T, Traitable

from ui_10x.table_view import TableView
from ui_10x.utils import UxAsync, ux


class MarketSymbol(Traitable):
    symbol: str     = RT(T.READONLY)
    bid: float      = RT()
    price: float    = RT()
    ask: float      = RT()
    prev_close: float = RT()

    dp: float           = RT(T.HIDDEN,  default = 0.)
    prev_price: float   = RT(T.HIDDEN)
    delta: float        = RT(T.HIDDEN)
    std: float          = RT(T.HIDDEN)
    delta_mean: float   = RT(T.HIDDEN)

    def delta_mean_get(self) -> float:
        return self.prev_close * 0.001

    def dp_set(self, trait, value) -> RC:
        self.prev_price = self.price
        return self.raw_set_trait_value(trait, value)

    def prev_price_get(self) -> float:
        return self.prev_close

    def price_get(self) -> float:
        return self.prev_price + self.dp

    def price_style_sheet(self) -> str:
        d = self.price - self.prev_close
        if d > 0:
            c = 'green'
        elif d < 0:
            c = 'red'
        else:
            c = 'black'
        return T.fg_color(c)

    def delta_get(self) -> float:
        mm = self.price # noqa: F841
        return random.gauss(self.delta_mean, self.std)

    def bid_get(self) -> float:
        mm = self.price
        if mm != None:
            mm -= self.delta
        return mm

    def ask_get(self) -> float:
        mm = self.price
        if mm != None:
            mm += self.delta
        return mm

class MarketMonitor:
    s_symbol_data = [
        ['symbol',  'prev_close',   'std'],
        ['MSFT',    398.04,         0.9],
        ['MS',      172.70,         0.5],
        ['JPM',     307.32,         0.7],
        ['IBM',     258.29,         0.15],
        ['GS',      918.30,         0.2],
        ['GOOG',    302.90,         0.3],
        ['NVDA',    188.50,         10.0 ],
        ['BAC',     52.74,          0.9],
        ['AMZN',    202.93,         0.8],
        ['AAPL',    263.47,         0.7],
    ]
    @classmethod
    def fetch_symbols(cls) -> list:
        res = []
        symbol_data = cls.s_symbol_data
        trait_names = symbol_data[0]
        n = len(trait_names)
        for row in range(1, len(symbol_data)):
            sym = MarketSymbol(**{trait_names[i]: symbol_data[row][i] for i in range(n)})
            try:
                sym.prev_close = yf.Ticker(sym.symbol).fast_info['previous_close']
            except Exception as e:
                print(f'yfinance lookup failed for {sym.symbol} ({e}); using fallback price')

            res.append(sym)

        return res

    def __init__(self):
        self.symbols = self.fetch_symbols()
        UxAsync.init(self.update_mkt_data)
        self.timer = threading.Timer(3, self.process_timer)
        self.next_item = 0

    def widget(self):
        self.table = table = TableView(MarketSymbol)
        self.timer.start()
        return table

    def update_mkt_data(self):
        i = self.next_item
        if i < len(self.symbols):
            self.table.extend_data([ self.symbols[i] ])
            self.next_item += 1

        symbols = self.table.model().m_data
        for row, symbol in enumerate(symbols):
            d = random.gauss(symbol.delta_mean, symbol.std)
            if random.randint(0, 10) < 5:
                d = -d
            symbol.dp = d
            self.table.render_traitable(row, symbol)

        dt = random.randint(0, 2)
        self.timer = threading.Timer(dt, self.process_timer)
        self.timer.start()

    def process_timer(self):
        UxAsync.call(self.update_mkt_data)

if __name__ == '__main__':
    from core_10x.exec_control import INTERACTIVE

    from ui_10x.examples.price_simulator import MarketSymbol
    from ui_10x.utils import UxDialog

    ux.init()

    with INTERACTIVE():
        mm = MarketMonitor()
        d = UxDialog(mm.widget(), title = 'Enjoy watching some stocks :-)')
        d.exec()

