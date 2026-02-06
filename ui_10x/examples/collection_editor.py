if __name__ == '__main__':
    from core_10x.code_samples.person import Person
    from core_10x.exec_control import INTERACTIVE
    from core_10x.ts_store import TsStore

    from ui_10x.collection_editor import Collection, CollectionEditor
    from ui_10x.utils import UxDialog, ux

    ux.init()

    with TsStore.instance_from_uri('mongodb://localhost/test'):
        with INTERACTIVE():
            coll = Collection(cls = Person)
            ce = CollectionEditor(coll = coll)
            w = ce.main_widget()
            d = UxDialog(w)
            d.exec()
