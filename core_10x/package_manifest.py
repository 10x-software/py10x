from core_10x.py_class import PyClass
from core_10x.resource import ResourceRequirements, TS_STORE
from core_10x.data_domain import GeneralDomain

class PackageManifest:
    """
    To associate a subclass of Traitable to a particular Data Domain Category
    it must have a record in a package manifest file.
    Example:
        # module x.etrading_domain
        class ETradingDomain(DataDomain):
            GENERAL     = TS_STORE()
            ORDERS      = TS_STORE()
            ALGO_ORDERS = TS_STORE()
            ...

        #module x.y.order
        class Order(Traitable):
            ...

        class AlgoOrder(Order):
            ...


        #module x.y._package_manifest
        from x.etrading_domain import ETradingDomain as ET

        manifest = dict(        #-- variable manifest: dict must be defined as follows
            _category = ET.GENERAL,     #-- default category for Traitables in x.y package, if any

            order = dict(                   #-- specific association(s) for any module inside x.y package, if any
                _category = ET.ORDERS           #-- default category for Traitables in x.y.order, if any

                AlgoOrder = ET.ALGO_ORDERS      #-- specific association class x.y.order.AlgoOrder, if any
                ...
            ),
            ...
        )

        If no association could be found for a subclass of Traitable, the default association will be used: GeneralDomain.GENERAL
    """
    SYMBOL      = '_package_manifest.manifest'
    CATEGORY    = '_category'

    @staticmethod
    def _resource_requirements(cls) -> ResourceRequirements:
        module = cls.__module__
        parts = module.split('.')
        if len(parts) < 2:
            return None     #-- should be at least package.module, so it's most probably '__main__.Class'

        package = '.'.join(parts[:-1])
        man_def: dict = PyClass.find_symbol(f'{package}.{PackageManifest.SYMBOL}')
        if not man_def:
            return None

        short_module = parts[-1]
        module_entry = man_def.get(short_module)
        if module_entry:
            rr: ResourceRequirements = module_entry.get(cls.__name__)
            if not rr:
                rr = module_entry.get(PackageManifest.CATEGORY)
                if rr:
                    return rr

        return man_def.get(PackageManifest.CATEGORY)

    @staticmethod
    def resource_requirements(cls) -> ResourceRequirements:
        rr = PackageManifest._resource_requirements(cls) or GeneralDomain.GENERAL
        assert rr.resource_type is TS_STORE, f'{cls} - invalid category in the _package_manifest'
        return rr

    #-- TODO: handle parent classes, if ResourceRequirements for the class in not found
