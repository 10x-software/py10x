import os
import sys
import tempfile
import importlib
from setuptools import Extension, Distribution
from Cython.Build import cythonize


def compile_sources(package_name: str, sources: dict):

    module_name = f"_cy_{package_name}"

    build_dir = tempfile.mkdtemp()
    pyx_path = os.path.join(build_dir, module_name + ".pyx")

    lines = [
        "# cython: language_level=3",
        "import cython",
        "",
    ]

    name_map = {}

    for cls, getters in sources.items():

        cls_name = cls.__name__

        for getter_name, cy_src in getters.items():

            fn_name = f"{cls_name}_{getter_name}"

            name_map[(cls, getter_name)] = fn_name

            # replace function name in source
            cy_src = cy_src.replace(
                f"def {getter_name}",
                f"def {fn_name}"
            )

            lines.append(cy_src)
            lines.append("")

    with open(pyx_path, "w", encoding="utf8") as f:
        f.write("\n".join(lines))

    ext = Extension(module_name, [pyx_path])

    dist = Distribution({
        "ext_modules": cythonize([ext], quiet=True)
    })

    dist.run_command("build_ext")

    build_ext = dist.get_command_obj("build_ext")
    sys.path.insert(0, build_ext.build_lib)

    module = importlib.import_module(module_name)

    compiled = {}

    for (cls, getter_name), fn_name in name_map.items():

        compiled.setdefault(cls, {})[getter_name] = getattr(module, fn_name)

    return compiled