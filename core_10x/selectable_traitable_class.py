from core_10x.traitable import T, Traitable


class SelectableTraitableRecord(Traitable):
    selectable_base_class: type     = T(T.ID)
    selected_class: type            = T()

class SelectableTraitableClass:
    """
    Mixin (deliberately not a Traitable) for classes whose concrete implementation should be
    swappable without touching call sites. Declaring no traits of its own means it can be
    added via multiple inheritance alongside a class's real, existing base chain instead of
    replacing it, e.g.:

        class ZeroRateCurve(TenorBasedSyntheticCurve, SelectableTraitableClass, ...):
            def payload_get(self): ...

    A company can then override the implementation without touching ZeroRateCurve's call sites:

        class CompanyZRC(ZeroRateCurve):
            def payload_get(self): ...

        SelectableTraitableRecord(selectable_base_class = ZeroRateCurve, selected_class = CompanyZRC, _replace = True).save()

    Callers then build via `ZeroRateCurve.selected_class()(**trait_values)` instead of
    `ZeroRateCurve(**trait_values)`, and transparently get CompanyZRC (or whatever is
    registered) instead. `selectable_base_class` is a `type` ID trait, so the registration
    survives a future PackageRefactoring.move_class() rename of the base class itself.
    """
    @classmethod
    def selected_class(cls) -> type[Traitable]:
        record = SelectableTraitableRecord.existing_instance(selectable_base_class = cls, _throw = False)
        return record.selected_class if record else cls
