from datetime import date

from core_10x.traitable import RC, RT, M, T, Traitable

from xxfin.mkt_conventions import MktConventions
from xxfin.snapshot import SNAPSHOT


class MktDataBasis(Traitable):
    provider_name: str  = T(T.ID | T.NOT_EMPTY) // 'Mkt Data Provider Name, e.g., BBG'  #-- using Enum seems not ideal due to extensions
    mkt_name: str       = T(T.ID | T.NOT_EMPTY) // 'Unique Market Name, e.g., SOFR'
    md_date: date       = T(T.ID | T.NOT_EMPTY) // 'Mkt Data Date'
    snapshot: SNAPSHOT  = T(T.ID | T.NOT_EMPTY, default = SNAPSHOT.CLOSE) // 'Mkt Data Date time snapshot, most often symbolic'

    md_basis: dict      = RT()

    mkt_conventions: MktConventions = RT()

    def mkt_conventions_get(self):
        mc_cls = self.T.mkt_conventions.data_type
        assert mc_cls and issubclass(mc_cls, MktConventions), 'mkt_conventions must be a subclass of MktConventions'
        return mc_cls.existing_instance(mkt_name = self.mkt_name)

    def md_basis_get(self) -> dict:
        return dict(
            mkt_name        = self.mkt_name,
            md_date         = self.md_date,
            provider_name   = self.provider_name,
            snapshot        = self.snapshot
        )

