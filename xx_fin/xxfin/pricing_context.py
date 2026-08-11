from __future__ import annotations

from datetime import date

from core_10x.named_constant import Enum
from core_10x.traitable import RT, T, Traitable

from xxfin.snapshot import SNAPSHOT
from xxfin.xxfin_env_vars import XXFinEnvVars


class PRICING_MODE(Enum):
    PRICING     = ()
    MKT_RISK    = ()

class SimplePricingContext(Traitable):
    """
    Trivial pricing context - it's not recommended for a real portfolio (more complex and realistic PC would use at least its own
    Cache Layer).
    """
    pricing_mode: PRICING_MODE  = T(PRICING_MODE.PRICING)

    mkt_data_provider_name: str = T(T.NOT_EMPTY)       // 'Mkt Data Provider Name, e.g., BBG'
    md_date: date               = T(T.NOT_EMPTY)       // 'Mkt Data Date'
    snapshot: SNAPSHOT          = T(SNAPSHOT.CLOSE)    // 'Mkt Data Date time snapshot, most often symbolic'

    md_basis: dict              = RT()  #-- TODO: EVAL_ONCE | READ_ONLY ?

    def md_basis_get(self) -> dict:
        return dict(
            provider_name   = self.mkt_data_provider_name,
            md_date         = self.md_date,
            snapshot        = self.snapshot,
        )

    s_current_pc = None
    @classmethod
    def current(cls) -> SimplePricingContext:
        pc = cls.s_current_pc
        assert pc, 'Current pricing context not set'
        return pc

    def end_using(self):
        assert self is PricingContext.s_current_pc, f'Using a different pricing context = {self.s_current_pc} != {self}'
        self.__class__.s_current_pc = None

    def begin_using(self):
        assert not PricingContext.s_current_pc, f'Already within a pricing context = {self.s_current_pc}'
        self.__class__.s_current_pc = self

    def __enter__(self):
        self.begin_using()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_using()

class PricingContext(SimplePricingContext):
    name: str   = T(T.ID)

    @classmethod
    def current(cls) -> PricingContext:
        pc = cls.s_current_pc
        if not pc:
            pc_name = XXFinEnvVars.default_pricing_context_name
            if not pc_name:
                raise AssertionError('No pricing context is set')

            pc = PricingContext.existing_instance(name = pc_name)
            pc.begin_using()

        return pc
