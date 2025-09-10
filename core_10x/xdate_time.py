from datetime import date, datetime

import dateutil.parser

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
            ym = v // 100

            month = ym % 100
            year = ym // 100

            return date(year = year, month = month, day = day)

        return date.fromordinal(v)

    def date_to_int(v: date, ordinal = True) -> int:
        return v.toordinal() if ordinal else (10000 * v.year + 100* v.month + v.day)

    FORMAT_X10  = '%Y%m%d'
    FORMAT_ISO  = '%Y-%m-%d'
    FORMAT_US   = '%m/%d/%Y'
    FORMAT_EU   = '%d.%m.%Y'

    s_default_format = FORMAT_X10
    formats = [s_default_format, FORMAT_X10, FORMAT_ISO, FORMAT_US, FORMAT_EU]

    @classmethod
    def set_default_format(cls, fmt: str):
        cls.s_default_format = fmt
        cls.formats[0] = fmt

    def str_to_date(v: str, format = '') -> date|None:
        if format:
            try:
                return datetime.strptime(v, format).date()
            except Exception:
                return None

        for fmt in XDateTime.formats:
            try:
                return datetime.strptime(v, fmt).date()
            except Exception:
                continue

        try:
            return dateutil.parser.parse(v).date()
        except Exception:
            pass


    formats_to_str = (
        f'{formats[0]} %H:%M:%S',
        f'{formats[0]} %H:%M:%S.%f',
    )
    def datetime_to_str(v: datetime, with_ms: bool = False) -> str:
        fmt = XDateTime.formats_to_str[with_ms]
        return v.strftime(fmt)

    def date_to_str(v: date, format = '') -> str:
        if not format:
            format = XDateTime.formats[0]
        return v.strftime(format)

    date_converters = {
        date:       lambda v:   v,
        datetime:   lambda v:   date(v.year, v.month, v.day),
        int:        int_to_date,
        str:        str_to_date,
    }
    @classmethod
    def to_date(cls, v) -> date|None:
        fn = cls.date_converters.get(type(v))
        return fn(v) if fn else None

    dt_format = ('%H:%M', '%H:%M:%S')
    def str_to_datetime(v: str) -> datetime|None:
        parts = v.split(' ')
        try:
            date_part, time_part = parts
            d = XDateTime.str_to_date(date_part)
            if d is not None:
                num_colons = time_part.count(':')
                fmt = XDateTime.dt_format[num_colons]
                if time_part.find('.') != -1:
                    fmt = fmt + '.%f'
                    return datetime.strptime(time_part, fmt)
        except Exception:
            pass

        try:
            return dateutil.parser.parse(v)
        except Exception:
            pass


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


