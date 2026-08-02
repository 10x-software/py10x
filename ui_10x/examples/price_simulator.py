import random
import threading

from core_10x.traitable import Traitable, T, RT, RC, RC_TRUE
from ui_10x.utils import ux, UxAsync
from ui_10x.table_view import TableView


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
    s_symbols = [
        dict(symbol = 'MSFT',  prev_close = 398.04,     std = 0.9 ),
        dict(symbol = 'MS',    prev_close = 172.70,     std = 0.5 ),
        dict(symbol = 'JPM',   prev_close = 307.32,     std = 0.7 ),
        dict(symbol = 'IBM',   prev_close = 258.29,     std = 0.15 ),
        dict(symbol = 'GS',    prev_close = 918.30,     std = 0.2 ),
        dict(symbol = 'GOOG',  prev_close = 302.90,     std = 0.3 ),
        dict(symbol = 'NVDA',  prev_close = 188.50,     std = 10.0 ),
        dict(symbol = 'BAC',   prev_close = 52.74,      std = 0.9 ),
        dict(symbol = 'AMZN',  prev_close = 202.93,     std = 0.8 ),
        dict(symbol = 'AAPL',  prev_close = 263.47,     std = 0.7 ),
    ]

    def __init__(self):
        UxAsync.init(self.update_mkt_data)
        self.timer = threading.Timer(3, self.process_timer)
        self.next_item = 0

    def widget(self):
        self.table = table = TableView(MarketSymbol)
        self.timer.start()
        return table

    def update_mkt_data(self):
        i = self.next_item
        if i < len(self.s_symbols):
            self.table.extend_data([ MarketSymbol(**self.s_symbols[i]) ])
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
    from ui_10x.utils import UxDialog
    from ui_10x.examples.price_simulator import MarketSymbol

    ux.init()

    with INTERACTIVE():
        mm = MarketMonitor()
        d = UxDialog(mm.widget(), title = 'Enjoy watching some stocks :-)')
        d.exec()

