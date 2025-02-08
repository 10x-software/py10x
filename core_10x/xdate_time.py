from datetime import datetime, date


MIN_CANONICAL_DATE = 10000101
class XDateTime:
    """
    All datetime values are in UTC time zone!
    """

    def int_to_date(v: int) -> date:
        """
        ordinal or canonical (<yyyy><mm><dd>)
        """
        if v >= MIN_CANONICAL_DATE:
            day = v % 100
            ym = v - day

            month = ym % 100
            year = ym - month

            return date(year = year, month = month, day = day)

        return date.fromordinal(v)

    def date_to_int(v: date, ordinal = True) -> int:
        return v.toordinal() if ordinal else (10000 * v.year + 100* v.month + v.day)

    formats = (
        '%Y%m%d',       #-- 10x
        '%Y-%m-%d',     #-- ISO
        '%m/%d/%Y',     #-- US
        '%d.%m.%Y',     #-- EU
    )
    def str_to_date(v: str) -> date:
        for fmt in XDateTime.formats:
            try:
                return datetime.strptime(v, fmt).date()
            except Exception:
                continue

        return None

    formats_to_str = (
        f'{formats[0]} %H:%M:%S',
        f'{formats[0]} %H:%M:%S.%f',
    )
    def datetime_to_str(v: datetime, with_ms: bool = False) -> str:
        fmt = XDateTime.formats_to_str[with_ms]
        return v.strftime(fmt)

    def date_to_str(v: date) -> str:
        return v.strftime(XDateTime.formats[0])

    date_converters = {
        date:       lambda v:   v,
        datetime:   lambda v:   date(v.year, v.month, v.day),
        int:        int_to_date,
        str:        str_to_date,
    }
    @classmethod
    def to_date(cls, v) -> date:
        fn = cls.date_converters.get(type(v))
        return fn(v) if fn else None

    dt_format = ('%H:%M', '%H:%M:%S')
    def str_to_datetime(v: str) -> datetime:
        parts = v.split(' ')
        try:
            date_part, time_part = parts
            d = XDateTime.str_to_date(date_part)
            if d is None:
                return None

            num_colons = time_part.count(':')
            try:
                fmt = XDateTime.dt_format[num_colons]
                if time_part.find('.') != -1:
                    fmt = fmt + '.%f'
                    return datetime.strptime(time_part, fmt)
            except Exception:
                return None

        except Exception:
            return None

    def date_to_datetime(d: date) -> datetime:
        return datetime(year = d.year, month = d.month, day = d.day)

    datetime_converters = {
        datetime:   lambda v:   v,
        date:       lambda v:   datetime(year = v.year, month = v.month, day = v.day),
        int:        lambda v:   XDateTime.date_to_datetime(XDateTime.int_to_date(v)),
        str:        str_to_datetime,
    }
    @classmethod
    def to_datetime(cls, v) -> datetime:
        fn = cls.datetime_converters.get(type(v))
        return fn(v) if fn else None


