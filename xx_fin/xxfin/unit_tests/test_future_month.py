from datetime import date

import pytest
from xxfin.future_month import FutureMonth


class TestFutureMonth:
    def test_fdate(self):
        assert FutureMonth('F2026').fdate == date(2026,1,1)
        assert FutureMonth('F26').fdate == date(2026,1,1)
        assert FutureMonth('f26').fdate == date(2026,1,1)
        assert FutureMonth('F60').fdate == date(1960,1,1)
        assert FutureMonth('F59').fdate == date(2059,1,1)


    def test_to_date_good(self):
        f_to_d = {
            'F26':      date(2026,1,1),
            'F2026':    date(2026,1,1),
            'H2030':    date(2030,3,1),
            'H30':      date(2030,3,1),
            'H59':      date(2059,3,1),
            'H60':      date(1960,3,1),
        }

        for f, d in f_to_d.items():
            # act = FutureMonth( f ).to_date(f)
            act = FutureMonth.to_date( f )
            assert act == d

    def test_to_date_bad(self):
        bad_f = {
            'W25':      'bad fut month',
            'X1855':    'bad fut year',
            'D12345':   'bad size/year',
            'AB123':    'bad month/year',
        }

        for f, msg in bad_f.items():
            try:
                FutureMonth.to_date(f)
            except AssertionError:
                pass
            else:
                pytest.fail(msg)

    def test_to_date2(self):
        with pytest.raises(AssertionError, match = 'Future D12345 should be of format <contract month symbol><year> with 2- or 4-digit year'):
            FutureMonth.to_date('D12345')
        with pytest.raises(AssertionError, match = 'Contract month P of P2000 must be one of the standard future contract months: FGHJKMNQUVXZ'):
            FutureMonth.to_date('P2000')
        with pytest.raises(AssertionError, match = 'Invalid contract year AB in FAB'):
            FutureMonth.to_date('FAB')
        with pytest.raises(AssertionError, match = 'Contract year of Z1800 must be greater than 1960'):
            FutureMonth.to_date('Z1800')

    def test_date_to_fut_month(self):
        assert FutureMonth.date_to_fut_month(date(2026, 1, 1)) == 'F2026'
        assert FutureMonth.date_to_fut_month(date(2026, 2, 15)) == 'G2026'
        assert FutureMonth.date_to_fut_month(date(2028, 2, 29)) == 'G2028'

        assert FutureMonth.date_to_fut_month(date(2026, 1, 1), two_digit_year=False) == 'F2026'
        assert FutureMonth.date_to_fut_month(date(2026, 1, 1), two_digit_year=True) == 'F26'

    def test_next_fut_month(self):
        assert FutureMonth.next_fut_month('f26') == 'G2026'  # lower case
        assert FutureMonth.next_fut_month('F26') == 'G2026'
        assert FutureMonth.next_fut_month('F2026') == 'G2026'
        assert FutureMonth.next_fut_month('f2026', next_num=1) == 'G2026'
        assert FutureMonth.next_fut_month('F2026', next_num=0) == 'F2026'
        assert FutureMonth.next_fut_month('F26',   next_num=0) == 'F26'

        assert FutureMonth.next_fut_month('F2026', next_num=2) == 'H2026'
        assert FutureMonth.next_fut_month('f2026', next_num=5) == 'M2026'
        assert FutureMonth.next_fut_month('F2026', next_num=11) == 'Z2026'
        assert FutureMonth.next_fut_month('F2026', next_num=12) == 'F2027'

        assert FutureMonth.next_fut_month('F60', next_num=0) == 'F60'
        assert FutureMonth.next_fut_month('F60', next_num=1) == 'G1960'


    def test_number_of_next_fut_months(self):
        assert FutureMonth.number_of_next_fut_months('F2026',0) == []
        assert FutureMonth.number_of_next_fut_months('F2026',0,1) == []
        assert FutureMonth.number_of_next_fut_months('F2026',0,0) == ['F2026']
        assert FutureMonth.number_of_next_fut_months('F2026',1) == ['G2026']
        assert FutureMonth.number_of_next_fut_months('F2026',2) == ['G2026', 'H2026']
        assert FutureMonth.number_of_next_fut_months('F2026',2, 0) == ['F2026', 'G2026', 'H2026']
        assert FutureMonth.number_of_next_fut_months('F2026',2, 1) == [         'G2026', 'H2026']
        assert FutureMonth.number_of_next_fut_months('F2026',2, 2) == [                  'H2026']
        assert FutureMonth.number_of_next_fut_months('F2026',2, 3) == []
        assert FutureMonth.number_of_next_fut_months('F2026',2, 10) == []

        assert FutureMonth.number_of_next_fut_months('F2026',0, -1) == ['Z2025', 'F2026']
        assert FutureMonth.number_of_next_fut_months('F2026',-1, -1) == ['Z2025']
        assert FutureMonth.number_of_next_fut_months('F2026',-1, -2) == ['X2025', 'Z2025']
        assert FutureMonth.number_of_next_fut_months('F2026',-2, -4) == ['U2025', 'V2025', 'X2025']

        with pytest.raises(AssertionError):
            FutureMonth.number_of_next_fut_months('A2026',-2, -4)


    def test_full_name(self):
        assert FutureMonth.full_name('F2026') == 'F2026'
        assert FutureMonth.full_name('f2026') == 'F2026'
        assert FutureMonth.full_name('F26') == 'F2026'
        assert FutureMonth.full_name('f26') == 'F2026'

        with pytest.raises(AssertionError):
            FutureMonth.full_name('A123')
        with pytest.raises(AssertionError):
            FutureMonth.full_name('ABC')

    def test_dunder(self):
        assert FutureMonth('F2026') == FutureMonth('f26')
        assert FutureMonth('F2026') != FutureMonth('G26')
        assert FutureMonth('F2026') <= FutureMonth('G26')
        assert FutureMonth('F2026') <= FutureMonth('F26')
        assert FutureMonth('F2026') <  FutureMonth('h26')
        assert FutureMonth('F2026') >  FutureMonth('z20')
        assert FutureMonth('F2026') >= FutureMonth('z20')

