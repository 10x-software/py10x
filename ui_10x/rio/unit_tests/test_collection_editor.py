import pytest
import rio.testing.browser_client
from core_10x.code_samples.person import Person
from core_10x.ts_union import TsUnion
from ui_10x.collection_editor import Collection, CollectionEditor
from ui_10x.rio.component_builder import DynamicComponent


@pytest.fixture(autouse=True)
def mock_db_ops(monkeypatch):
    with TsUnion():
        sasha = Person(first_name='Sasha', last_name='Davidovich')
        ilya = Person(first_name='Ilya', last_name='Pevzner')
    monkeypatch.setattr(Person, 'load_ids', lambda: [sasha.id(), ilya.id()])
    monkeypatch.setattr(Person, 'load_data', lambda id: {sasha.id(): sasha, ilya.id(): ilya}[id])
    yield


async def test_collection_editor() -> None:
    coll = Collection(cls=Person)
    ce = CollectionEditor(coll=coll)
    widget = ce.main_widget()

    async with rio.testing.BrowserClient(lambda: DynamicComponent(widget)) as test_client:
        pass
