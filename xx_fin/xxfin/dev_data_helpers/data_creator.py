from xxfin.snapshot import SNAPSHOT


class DataCreator:
    @classmethod
    def create(cls, data_class, data: tuple, extra_action = None, save = True):
        for data_item in data:
            o = data_class(
                _replace = True,
                **data_item
            )
            if save:
                o.save().throw()
            if extra_action:
                extra_action(o)

    """
    fx_data = {
    date(2025, 10, 10): {
        'GBP/USD':   {
            FXSpotQuotable:     ((), (1.3174,)),  ## presence of the class matters, tenor is irrelevant
            FXForwardQuotable:  (
                ('1B',      '1W',   '1M',       '3M',       '6M',       '9M',       '12M',      '2Y',       '5Y',       '20Y'),
                (1.31739,   1.31738, 1.31735,   1.31742,    1.31745,    1.31725,    1.3165,     1.31157,    1.2989,     1.26649)
            )
        },
        'EUR/USD': {
            FXSpotQuotable:     ((), (1.16018,)),  ## presence of the class matters, tenor is irrelevant
            FXForwardQuotable:  (
                ('1B',      '1W',       '1M',       '3M',       '6M',       '9M',       '12M',      '2Y',       '5Y',       '10Y'   ),
                (1.16024,   1.16069,    1.16221,    1.16603,    1.17101,    1.17564,    1.1797,     1.19362,    1.23218,     1.30417)
            )
        },
    """
    @classmethod
    def create_mkt_data_with_timetag(cls, mkt_data: dict, timetag_class_or_fn_tag: tuple, provider_name = 'XX_DEV', snapshot = SNAPSHOT.CLOSE, save = True):
        try:
            timetag_class_or_fn, timetag_tag = timetag_class_or_fn_tag
        except Exception as e:
            raise AssertionError(f'Invalid timetag_class_or_fn_tag: {timetag_class_or_fn_tag} - (timetag_class_or_fn, timetag_tag) expected, e.g. (Rdate, "tenor")' ) from e

        for md_date, data_per_mkt in mkt_data.items():
            for mkt_name, data_per_class in data_per_mkt.items():
                for quote_class, tenors_and_quotes in data_per_class.items():
                    try:
                        timetags, quotes = tenors_and_quotes
                    except Exception as e:
                        raise ValueError(f'{md_date}: {mkt_name}: {quote_class}: ( (tenors,), (quotes,) ) is expected') from e

                    assert len(timetags) == len(quotes), f'{md_date}: {mkt_name}: {quote_class} has misaligned timetags and quotes'
                    for i in range(len(timetags)):
                        trait_values = dict(
                            _replace        = True,
                            provider_name   = provider_name,
                            mkt_name        = mkt_name,
                            md_date         = md_date,
                            snapshot        = snapshot,
                            quote           = quotes[i]
                        )
                        if timetags[i]:
                            trait_values[timetag_tag] = timetag_class_or_fn(timetags[i]) if timetag_class_or_fn else timetags[i]

                        quote_object = quote_class(**trait_values)
                        if save:
                            quote_object.save().throw()
