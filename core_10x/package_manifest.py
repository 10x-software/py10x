from core_10x.py_class import PyClass
from core_10x.resource import ResourceRequirements

class PackageManifest:
    SYMBOL      = '_package_manifest.manifest'
    CATEGORY    = '_category'

    @staticmethod
    def resource_requirements(cls) -> ResourceRequirements:
        module = cls.__module__
        parts = module.split('.')
        assert len(parts) >= 2, f'{cls} - invalid class'
        package = '.'.join(parts[:-1])
        man_def: dict = PyClass.find_symbol(f'{package}.{PackageManifest.SYMBOL}')
        if not man_def:
            return None

        short_module = parts[-1]
        module_entry = man_def.get(short_module)
        if module_entry:
            rr: ResourceRequirements = module_entry.get(cls.__name__)
            if rr:
                return rr

        return man_def.get(PackageManifest.CATEGORY)

    #-- TODO: handle parent classes, if ResourceRequirements for the class in not found
