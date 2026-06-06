from datetime import date, timedelta

from core_10x.xdate_time import XDateTime
from core_10x.logger import PerfTimer
from xx_common.curve import DateCurve, IP_KIND

c = DateCurve()

d1 = date(2020, 2, 1)
#c.update(d1, 10.)

# dates_i = [ 20200105,   20200205,   20200305,   20210605,   20211105,   20230305 ]
# values  = [ 1,          2,          3,          4,          5,          6 ]
# dates = [XDateTime.to_date(v) for v in dates_i]

dt = timedelta(days = 10)
dates = []
values = []
d = d1
v = 1.
for i in range(1000):
    dates.append(d)
    values.append(v)
    d = d + dt
    v = v + 2
rdt = timedelta(days = 20)

with PerfTimer() as t:
    c.update_many(dates, values)

    # rdates = [
    #     date(2020, 1, 21),
    #     date(2020, 4, 1),
    #     date(2021, 7, 8),
    #     date(2022, 9, 1),
    #     date(2023   , 10, 1),
    # ]

    results = [
        c.value(d + rdt) for d in dates
    ]
print(t.elapsed)
