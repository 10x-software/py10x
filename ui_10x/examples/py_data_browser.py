from datetime import date
from ui_10x.utils import ux
from ui_10x.py_data_browser import PyDataBrowser

from core_10x.py_class import PyClass


class A:
    pass


class B:
    def __repr__(self):
        return f'class {self.__class__.__name__} stub'

data = {
    'Plain int': 33,
    'Boolean': True,
    'All': (False, True),
    'Just None': None,
    'Now': date.today(),
    'A simple list': [ 100, 'abracadabra', 375.89 ],
    'A simple dict': dict(_a = 10, _b = None, _c = 'Atlantic Ocean'),
    'Unknown': A(),
    'Unknown, but': B(),

    'Nested Dict': dict(
        person = dict(
            first_name = 'Mike',
            last_name = 'Fellows',
            age = 50,
            countries = ('USA', 'Japan', 'Korea'),
        ),
        regions = [
            'Europe',
            dict(
                North = [ 'Canada', 'USA', 'Mexico' ],
                Central = [ 'Nicaragua', 'Costa Rica', 'Equador' ],
                South = [ 'Brasil', 'Argentina' ],
            ),
            'Asia',
        ],
    ),
    # 'People':           Person.generateList( _cache_only = True )
}

def on_select(browser: PyDataBrowser, path: list, value, delims = ('/', '/')):
    path_text = PyDataBrowser.path_to_str(path, delims)
    return print(f"'{path_text}' -> {value}")


if __name__ == '__main__':
    ux.init()

    PyDataBrowser.show([10, 'a'], on_select = on_select)

    PyDataBrowser.edit(
        data,
        on_select = lambda browser, path, value: on_select(browser, path, value, delims = ('[]', '[]'))
    )

    PyDataBrowser.show(
        PyClass.class_names_by_module('core_10x'),
        on_select = lambda browser, path, value: on_select(browser, path, value, delims = ('.', ''))
    )
