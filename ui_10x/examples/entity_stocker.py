if __name__ == '__main__':
    from core_10x.code_samples.person import Person
    from core_10x.exec_control import INTERACTIVE
    from core_10x.ts_store import TsStore

    from ui_10x.entity_stocker import EntityStocker, StockerPlug
    from ui_10x.utils import UxDialog, ux

    ux.init()

    with TsStore.instance_from_uri('mongodb://localhost/test'):
        plug = StockerPlug(current_class = Person)
        se = EntityStocker(plug = plug)

        with INTERACTIVE() as graph:
            w = se.main_widget()
            d = UxDialog(w)
            rc = d.exec()
