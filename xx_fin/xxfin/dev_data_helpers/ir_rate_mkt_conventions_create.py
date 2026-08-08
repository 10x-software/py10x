from core_10x.exec_control import CONVERT_VALUES_ON

from xxfin.ccy import Ccy
from xxfin.dev_data_helpers.data_creator import DataCreator
from xxfin.ir_rate_mkt_conventions import COMPOUNDING, DAY_COUNT_CONVENTION, FIXING_CONVENTION, TENOR_FREQUENCY, IRRateMktConventions
from xxfin.mkt_conventions import BIZDAY_ROLL_RULE, FinCalendar, RDate

data = (
    dict(
        mkt_name                = 'SOFR',
        ccy                     = 'USD',
        calendar                = 'US|',

        settle_offset           = RDate('2B'),
        roll_rule_to_settle     = BIZDAY_ROLL_RULE.FOLLOWING,
        settlement_calendar     = 'FD|',
        spot_offset             = RDate('2B'),
        fixing_offset           = RDate('-1B'),
        roll_rule_for_fixing    = BIZDAY_ROLL_RULE.FOLLOWING,
        roll_rule               = BIZDAY_ROLL_RULE.MOD_FOLLOWING,

        dc_convention           = DAY_COUNT_CONVENTION.ACT360,
        compounding             = COMPOUNDING.SIMPLE,

        fixing_frequency        = RDate('1B'),

        #-- floating leg
        tenor_frequency         = TENOR_FREQUENCY.YEAR,
        fixing_convention       = FIXING_CONVENTION.IN_ARREARS,

        #-- fixed leg
        fixed_leg_swap_dc_convention    = DAY_COUNT_CONVENTION.ACT360,
        fixed_leg_swap_compounding      = COMPOUNDING.SIMPLE,
        fixed_leg_swap_tenor_frequency  = TENOR_FREQUENCY.YEAR
    ),
    dict(
        mkt_name                = 'SONIA',
        ccy                     = 'GBP',
        calendar                = 'GB|',

        settle_offset           = RDate('2B'),
        roll_rule_to_settle     = BIZDAY_ROLL_RULE.FOLLOWING,
        settlement_calendar     = 'GB|',
        spot_offset             = RDate('2B'),
        fixing_offset           = RDate( '-1B'),
        roll_rule_for_fixing    = BIZDAY_ROLL_RULE.FOLLOWING,
        roll_rule               = BIZDAY_ROLL_RULE.MOD_FOLLOWING,

        dc_convention           = DAY_COUNT_CONVENTION.ACT365,
        compounding             = COMPOUNDING.SIMPLE,

        fixing_frequency        = RDate('1B'),

        #-- floating leg
        tenor_frequency         = TENOR_FREQUENCY.YEAR,
        fixing_convention       = FIXING_CONVENTION.IN_ARREARS,

        #-- fixed leg
        fixed_leg_swap_dc_convention    = DAY_COUNT_CONVENTION.ACT365,
        fixed_leg_swap_compounding      = COMPOUNDING.SIMPLE,
        fixed_leg_swap_tenor_frequency  = TENOR_FREQUENCY.YEAR
    ),

    ## TODO: totally meaningless data just as a place holder for TONA; TO BE FIXED
    dict(
        mkt_name            = 'TONA',
        ccy                 = 'JPY',
        calendar            = 'JP|',

        settle_offset       = RDate('2B'),
        roll_rule_to_settle = BIZDAY_ROLL_RULE.FOLLOWING,
        settlement_calendar = 'JP|',
        spot_offset         = RDate('2B'),
        fixing_offset       = RDate('-1B'),
        roll_rule_for_fixing= BIZDAY_ROLL_RULE.FOLLOWING,
        roll_rule           = BIZDAY_ROLL_RULE.MOD_FOLLOWING,

        dc_convention       = DAY_COUNT_CONVENTION.ACT365,
        compounding         = COMPOUNDING.SIMPLE,

        fixing_frequency    = RDate('1B'),

        # -- floating leg
        tenor_frequency     = TENOR_FREQUENCY.YEAR,
        fixing_convention   = FIXING_CONVENTION.IN_ARREARS,

        # -- fixed leg
        fixed_leg_swap_dc_convention    = DAY_COUNT_CONVENTION.ACT365,
        fixed_leg_swap_compounding      = COMPOUNDING.SIMPLE,
        fixed_leg_swap_tenor_frequency  = TENOR_FREQUENCY.YEAR
    ),
    dict(
        mkt_name                = 'CORRA',
        ccy                     = 'CAD',
        calendar                = 'CA|',

        settle_offset           = RDate('2B'),
        roll_rule_to_settle     = BIZDAY_ROLL_RULE.FOLLOWING,
        settlement_calendar     = 'CA|',
        spot_offset             = RDate('1B'),
        fixing_offset           = RDate('-1B'),
        roll_rule_for_fixing    = BIZDAY_ROLL_RULE.FOLLOWING,
        roll_rule               = BIZDAY_ROLL_RULE.MOD_FOLLOWING,

        dc_convention           = DAY_COUNT_CONVENTION.ACT365,
        compounding             = COMPOUNDING.SIMPLE,

        fixing_frequency        = RDate('1B'),

        #-- floating leg
        tenor_frequency         = TENOR_FREQUENCY.YEAR,
        fixing_convention       = FIXING_CONVENTION.IN_ARREARS,

        #-- fixed leg
        fixed_leg_swap_dc_convention    = DAY_COUNT_CONVENTION.ACT365,
        fixed_leg_swap_compounding      = COMPOUNDING.SIMPLE,
        fixed_leg_swap_tenor_frequency  = TENOR_FREQUENCY.YEAR
    ),
    ## TODO: check all the data below - placeholder for ESTR; TO BE FIXED
    dict(
        mkt_name='ESTR',
        ccy='EUR',
        calendar='EUTA|',

        settle_offset=RDate('2B'),
        roll_rule_to_settle=BIZDAY_ROLL_RULE.FOLLOWING,
        settlement_calendar='EUTA|',
        spot_offset=RDate('1B'),
        fixing_offset=RDate('-1B'),
        roll_rule_for_fixing=BIZDAY_ROLL_RULE.FOLLOWING,
        roll_rule=BIZDAY_ROLL_RULE.MOD_FOLLOWING,

        dc_convention=DAY_COUNT_CONVENTION.ACT365,
        compounding=COMPOUNDING.SIMPLE,

        fixing_frequency=RDate('1B'),

        # -- floating leg
        tenor_frequency=TENOR_FREQUENCY.YEAR,
        fixing_convention=FIXING_CONVENTION.IN_ARREARS,

        # -- fixed leg
        fixed_leg_swap_dc_convention=DAY_COUNT_CONVENTION.ACT365,
        fixed_leg_swap_compounding=COMPOUNDING.SIMPLE,
        fixed_leg_swap_tenor_frequency=TENOR_FREQUENCY.YEAR
    ),
    ## TODO: check all the data below - placeholder for SARON; TO BE FIXED
    dict(
        mkt_name='SARON',
        ccy='CHF',
        calendar='SZ|',

        settle_offset=RDate('2B'),
        roll_rule_to_settle=BIZDAY_ROLL_RULE.FOLLOWING,
        settlement_calendar='SZ|',
        spot_offset=RDate('1B'),
        fixing_offset=RDate('-1B'),
        roll_rule_for_fixing=BIZDAY_ROLL_RULE.FOLLOWING,
        roll_rule=BIZDAY_ROLL_RULE.MOD_FOLLOWING,

        dc_convention=DAY_COUNT_CONVENTION.ACT365,
        compounding=COMPOUNDING.SIMPLE,

        fixing_frequency=RDate('1B'),

        # -- floating leg
        tenor_frequency=TENOR_FREQUENCY.YEAR,
        fixing_convention=FIXING_CONVENTION.IN_ARREARS,

        # -- fixed leg
        fixed_leg_swap_dc_convention=DAY_COUNT_CONVENTION.ACT365,
        fixed_leg_swap_compounding=COMPOUNDING.SIMPLE,
        fixed_leg_swap_tenor_frequency=TENOR_FREQUENCY.YEAR
    ),
)

def run():
    with CONVERT_VALUES_ON():
        DataCreator.create(IRRateMktConventions, data)


if __name__ == '__main__':
    run()
