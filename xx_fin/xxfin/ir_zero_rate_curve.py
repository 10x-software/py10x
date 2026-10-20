from datetime import date

from core_10x.selectable_traitable_class import SelectableTraitableClass
from xxcommon.rdate import BIZDAY_ROLL_RULE, PROPAGATE_DATES, TENOR_FREQUENCY, RDate

from xxfin.fin_calendar import FinCalendar
from xxfin.ir_cash_deposit_quotable import IRCashDepositQuotable, IRRateMktConventions
from xxfin.ir_compounding import COMPOUNDING
from xxfin.ir_swap_quotable import IRSwapQuotable
from xxfin.ir_zero_rate_curve_mas import IRZeroRateCurveMas
from xxfin.rate_curve import RateCurve
from xxfin.synthetic_mkt_data import RT, M, T, TenorBasedSyntheticCurve
from xxfin.zrc_bootstrap import solve_cash_deposit, solve_swap

_DBG    = False

class ZeroRateCurve(TenorBasedSyntheticCurve, SelectableTraitableClass, mas_class = IRZeroRateCurveMas):
    mkt_conventions: IRRateMktConventions   = M()
    payload: RateCurve                      = M(T.EMBEDDED)

    def quotables_by_class_get(self) -> dict:
        today           = self.md_date
        mkt_basis       = self.md_basis
        mao             = self.mkt_assembly_object

        #-- pay_date already accounts for the '1B' start-today override (via start_date_get) and
        #   the tenor-roll + pay-lag chain (via end_date_get/pay_date_get on the quotable itself),
        #   so it doesn't need to be re-derived here.
        result = {}
        for quotable_class, data_definition in mao.quotable_stubs_by_class.items():
            quotable_by_date = {}
            result[quotable_class] = quotable_by_date
            for stub in mao.create_quotable_stubs(quotable_class, data_definition, today):
                quotable = quotable_class.existing_instance(**stub, **mkt_basis)
                quotable_by_date[quotable.pay_date] = quotable

        return result

    def payload_get(self) -> RateCurve:
        today = self.md_date
        mc = self.mkt_conventions
        res = RateCurve(beginning_of_time = today, quoting_dc_convention = mc.dc_convention, quoting_compounding = mc.compounding)

        self.process_cash_deposits(res)
        self.process_swaps(        res)
        res.set_curve_params_to_flat_extrapolate()

        return res

    def process_cash_deposits(self, zrc: RateCurve):
        today     = self.md_date
        mc        = self.mkt_conventions
        spot_date = mc.spot_date(today)

        if _DBG:    # pragma: no cover
            dc_convention = mc.dc_convention
            compounding   = mc.compounding
            cal           = mc.calendar
            roll_rule     = mc.roll_rule
            print(f'cash params: today = {today}/{today.strftime("%A")}, spot_date = {spot_date}/{spot_date.strftime("%A")}, dc_convention = {dc_convention.name}, compounding = {compounding.name}, '
                  f'cal = {cal.name}, roll = {roll_rule.name}\n')

        quotables = self.quotables_by_class.get(IRCashDepositQuotable)
        if not quotables:
            return

        quotable: IRCashDepositQuotable
        for end_date, quotable in quotables.items():
            start_date = quotable.start_date

            if _DBG: print(f'cash depo tenor = {quotable.tenor.symbol()}, start_date = {start_date}/{start_date.strftime("%A")}, end_date = {end_date}/{end_date.strftime("%A")}, quote = {quotable.quote}, ')  # pragma: no cover

            solve_cash_deposit(zrc, start_date, end_date, quotable.quote, mc, today)

            if _DBG:    # pragma: no cover
                dc_convention = mc.dc_convention
                compounding   = mc.compounding
                quote_acc  = zrc.fixed_rate_accrual(quotable.quote, start_date, end_date, dc_convention, compounding)
                zrc_acc    = zrc.accrual_fwd(start_date, end_date, today)
                float_rate = zrc.rate_fwd(start_date, end_date, dc_convention, compounding, today)
                print(f'quote acc = {quote_acc:.18f};    float acc  = {zrc_acc:.18f};    diff acc   = {zrc_acc - quote_acc}')
                print(f'quote df  = {1./quote_acc:.18f}; float df   = {1./zrc_acc:.18f}; diff df    = {1./zrc_acc - 1./quote_acc}')
                print(f'quote     = {quotable.quote:.18f};        float rate = {float_rate:.18f}; diff rates = {float_rate - quotable.quote}\n')

    def process_swaps(self, zrc: RateCurve):
        quotables = self.quotables_by_class.get(IRSwapQuotable)
        if not quotables:
            return

        mc = self.mkt_conventions

        float_compound = mc.compounding
        fixed_compound = mc.fixed_leg_swap_compounding
        simple         = COMPOUNDING.SIMPLE
        if (float_compound, fixed_compound) != (simple, simple):
            raise AssertionError(f'currently zero rate curve calibration supports only swaps with SIMPLE compounding, while the {mc.mkt_name} swaps have fixed/floating compounding {fixed_compound}/{float_compound}')

        today     = self.md_date
        spot_date = mc.spot_date(today)

        if _DBG:    # pragma: no cover
            fixed_dc_convention = mc.fixed_leg_swap_dc_convention
            pay_calendar        = mc.settlement_calendar
            pay_roll_rule       = mc.roll_rule_to_settle
            pay_offset: RDate   = mc.settle_offset
            print(f'swap params: today = {today}/{today.strftime("%A")}, spot_date = {spot_date}/{spot_date.strftime("%A")}, fixed_dc_convention = {fixed_dc_convention.name}, '
                  f'swap_cal = {mc.calendar.name}, swap_roll = {mc.roll_rule.name},\n '
                  f'pay_calendar = {pay_calendar.name}, pay_roll_rule = {pay_roll_rule.name}, pay_delay = {pay_offset.symbol()}, \n')

        quotable: IRSwapQuotable
        for quotable in quotables.values():
            tenor = quotable.tenor

            if _DBG:    # pragma: no cover
                fixed_freq: RDate = RDate(freq=mc.fixed_leg_swap_tenor_frequency, count=1)
                end_date_dbg = tenor.apply(spot_date, mc.calendar, mc.roll_rule)
                print(f'swap tenor/freq = {tenor.symbol()}/{fixed_freq.symbol()}, start_date = {spot_date}/{spot_date.strftime("%A")}, end_date = {end_date_dbg}/{end_date_dbg.strftime("%A")}, swap quote = {quotable.quote}, ')

            solve_swap(zrc, spot_date, tenor, quotable.quote, mc, today)

            if _DBG:    # pragma: no cover
                fixed_dc_convention = mc.fixed_leg_swap_dc_convention
                fixed_freq          = RDate(freq=mc.fixed_leg_swap_tenor_frequency, count=1)
                pay_offset          = mc.settle_offset
                pay_calendar        = mc.settlement_calendar
                pay_roll_rule       = mc.roll_rule_to_settle
                swap_rate = zrc.swap_rate_simple_compounding(
                    spot_date, tenor,
                    fixed_freq, fixed_dc_convention, mc.calendar, mc.roll_rule,
                    pay_offset, pay_calendar, pay_roll_rule,
                    PROPAGATE_DATES.FORWARD, False,
                )
                print(f'quote = {quotable.quote}, swap_rate = {swap_rate}, swap_rate - quote = {swap_rate - quotable.quote}\n')

