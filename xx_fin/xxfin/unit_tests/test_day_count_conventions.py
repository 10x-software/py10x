from datetime import date

import pytest

DAY_COUNT_CONVENTION = None

cases = {
    (date(2025,1,1), date(2026,1,1)):
    {
        '_name':    'non-leap year Jan 1st to Jan 1st',
        'act360': 365. / 360.,
        'act365': 1.,
        'actact': 1.,
        'bb30360': 1.,

    },
    (date(2027, 12, 31), date(2028, 12, 31)):
    # (date(2028, 1, 1), date(2029, 1, 1)):
        {
            '_name': 'leap year Dec 31st to Dec 31st',
            'act360': 366. / 360.,
            'act365': 366. / 365.,
            'actact': 1./365. + 365./366.,
            'bb30360': 1.,
            'us30360': 1.,
            'eb30360': 1.,
        },
    (date(2028, 1, 1), date(2029, 1, 1)):
        {
            '_name': 'leap year Jan 1st to Jan 1st',
            'act360': 366. / 360.,
            'act365': 366. / 365.,
            'actact': 1.,
            'bb30360': 1.,
            'us30360': 1.,
            'eb30360': 1.,
        },
    (date(2028, 2, 29), date(2028, 3, 31)):
        {
            '_name': 'leap Feb/Mar',
            'act360': 31. / 360.,
            'act365': 31. / 365.,
            'actact': 31. / 366.,
            'bb30360': 1./12. + 2./360.,
            'us30360': 1./12.,
            'eb30360': 1./12. + 1./360.,
        },
    (date(2028, 1, 31), date(2028, 2, 29)):
        {
            '_name': 'leap Jan/Feb',
            'act360': 29. / 360.,
            'act365': 29. / 365.,
            'actact': 29. / 366.,
            'bb30360': 1./12. - 1./360.,
            'us30360': 1./12. - 1./360.,
            'eb30360': 1./12. - 1./360.,
        },
    (date(2026, 1, 31), date(2026, 2, 28)):
        {
            '_name': 'non-leap Jan/Feb',
            'act360': 28. / 360.,
            'act365': 28. / 365.,
            'actact': 28. / 365.,
            'bb30360': 1./12. - 2./360.,
            'us30360': 1./12. - 2./360.,
            'eb30360': 1./12. - 2./360.,
        },
    (date(2028, 2, 1), date(2028, 3, 1)):
        {
            '_name': 'leap Feb',
            'act360': 29. / 360.,
            'act365': 29. / 365.,
            'actact': 29. / 366.,
            'bb30360': 1./12.,
            'us30360': 1./12.,
            'eb30360': 1./12.,
        },
    (date(2026, 2, 1), date(2026, 3, 1)):
        {
            '_name': 'non-leap Feb',
            'act360': 28. / 360.,
            'act365': 28. / 365.,
            'actact': 28. / 365.,
            'bb30360': 1. / 12.,
            'us30360': 1. / 12.,
            'eb30360': 1. / 12.,
        },
    (date(2000, 2, 1), date(2000, 3, 1)):
        {
            '_name': 'leap/400 Feb',
            'act360': 29. / 360.,
            'act365': 29. / 365.,
            'actact': 29. / 366.,
            'bb30360': 1. / 12.,
            'us30360': 1. / 12.,
            'eb30360': 1. / 12.,
        },
    (date(2100, 2, 1), date(2100, 3, 1)):
        {
            '_name': 'non-leap/100 Feb',
            'act360': 28. / 360.,
            'act365': 28. / 365.,
            'actact': 28. / 365.,
            'bb30360': 1. / 12.,
            'us30360': 1. / 12.,
            'eb30360': 1. / 12.,
        },

}

EPS = 1.e-6

_DC_KEYS = {
    'act360':  'ACT360',
    'act365':  'ACT365',
    'actact':  'ACTACT',
    'bb30360': 'BB30360',
    'us30360': 'US30360',
    'eb30360': 'EB30360',
}


@pytest.fixture(autouse=True)
def rebind_globals(cxx_or_py_day_count_convention):
    global DAY_COUNT_CONVENTION
    from xxfin.day_count_convention import DAY_COUNT_CONVENTION
    yield


@pytest.mark.parametrize('key', list(_DC_KEYS))
@pytest.mark.parametrize(
    'dates',
    list(cases),
    ids=[f'{d1}-{d2}' for d1, d2 in cases],
)
def test_day_count(key, dates):
    dcs = cases[dates]
    if key not in dcs:
        pytest.skip(f'{key} not defined for {dcs["_name"]}')
    dc = getattr(DAY_COUNT_CONVENTION, _DC_KEYS[key])
    assert dcs[key] == dc(*dates), dcs['_name']
