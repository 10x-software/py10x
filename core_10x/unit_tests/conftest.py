import sys
import uuid

import pytest
from core_10x.callable_instrumentation import CallableRewriter, InstrumentationRegistry


@pytest.fixture
def modules(tmp_path, monkeypatch):
    """Writes {short_name: source} as uniquely named modules; '{name}' in a source is replaced by that module's real name."""
    tag = uuid.uuid4().hex
    created = []

    def write(sources: dict[str, str]) -> dict[str, str]:
        names = {short: f'itr_{short}_{tag}' for short in sources}
        for short, source in sources.items():
            (tmp_path / f'{names[short]}.py').write_text(source.format(**names))
        created.extend(names.values())
        return names

    monkeypatch.syspath_prepend(str(tmp_path))
    yield write
    for name in created:
        sys.modules.pop(name, None)


@pytest.fixture
def registry():
    registry = InstrumentationRegistry(CallableRewriter())
    registry.enable_auto_instrumentation()
    yield registry
    registry.disable_auto_instrumentation()
