if __name__ == '__main__':
    from core_10x.code_samples.person import Person

    from infra_10x.mongodb_store import MongoStore

    from ui_10x.utils import ux, UxDialog
    from ui_10x.entity_stocker import EntityStocker, StockerPlug

    ux.init()

    with MongoStore.instance(hostname = 'localhost', dbname = 'test', username = '', password = ''):
        plug = StockerPlug()
        plug.current_class = Person

        se = EntityStocker()
        se.plug = plug

        w = ux.Widget()
        w.set_layout(se.main_layout())
        d = UxDialog(w)
        rc = d.exec()
