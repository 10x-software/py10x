from core_10x.named_constant import NamedConstant
from core_10x.traitable import RT, THIS_CLASS, T
from xxcommon.rdate import TENOR_FREQUENCY, RDate

from xxfin.day_count_convention import DAY_COUNT_CONVENTION
from xxfin.ir_compounding import COMPOUNDING
from xxfin.mkt_conventions import SpotMktConventions


class FIXING_CONVENTION(NamedConstant):
    IN_ADVANCE  = ()
    IN_ARREARS  = ()

## TODO: should we use spot_date calc-ed off ccy calendar and roll_rule or have its own here?
class IRRateMktConventions(SpotMktConventions):
    'IR Rate (e.g., SOFR) Conventions'

    dc_convention: DAY_COUNT_CONVENTION = T(DAY_COUNT_CONVENTION.ACT360)    // 'Day Count Convention'
    compounding: COMPOUNDING            = T(COMPOUNDING.SIMPLE)             // 'Rate Compounding'

    disc_mkt_name: str                  = RT()
    disc_mkt_conventions: THIS_CLASS    = RT()
    fixing_frequency: RDate             = T(RDate('1B'))

    #-- floating leg
    tenor_frequency: TENOR_FREQUENCY    = T(TENOR_FREQUENCY.YEAR)           // 'Floating Leg Standard Swap Frequency, e.g., HALF_YEAR, QUARTER'
    fixing_convention: FIXING_CONVENTION = T(FIXING_CONVENTION.IN_ARREARS)  // 'Floating Leg Standard Swap Fixing Convention'

    # TODO: fixing_calendar?

    #-- fixed leg
    fixed_leg_swap_dc_convention: DAY_COUNT_CONVENTION = T(DAY_COUNT_CONVENTION.ACT360)    // 'Fixed Leg Standard Swap Day Count Convention'
    fixed_leg_swap_compounding: COMPOUNDING            = T(COMPOUNDING.SIMPLE)             // 'Fixed Leg Standard Swap Rate Compounding'
    fixed_leg_swap_tenor_frequency: TENOR_FREQUENCY    = T(TENOR_FREQUENCY.YEAR)           // 'Fixed Leg Standard Swap Frequency'

    def disc_mkt_name_get(self) -> str:
        return self.ccy.discounting_mkt_name

    def disc_mkt_conventions_get(self):
        mkt_name = self.disc_mkt_name
        mc = self.__class__.existing_instance(mkt_name = mkt_name, _throw = False)
        if not mc:
            raise ValueError(f"'{mkt_name}' - unknown discounting mkt conventions")

        return mc

