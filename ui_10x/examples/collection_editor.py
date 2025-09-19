if __name__ == '__main__':
    from core_10x.code_samples.person import Person
    from core_10x.exec_control import INTERACTIVE
    from infra_10x.mongodb_store import MongoStore

    from ui_10x.collection_editor import Collection, CollectionEditor
    from ui_10x.utils import UxDialog, ux

    ux.init()

    with MongoStore.instance(hostname = 'localhost', dbname = 'test', username = '', password = ''):
        with INTERACTIVE():
            coll = Collection(cls = Person)
            ce = CollectionEditor(coll = coll)
            w = ce.main_widget()
            d = UxDialog(w)
            d.exec()
