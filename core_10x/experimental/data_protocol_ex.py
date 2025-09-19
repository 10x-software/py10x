import functools


class T:
    def __init__(self, name, get, *args):
        self.name = name
        self.get = get
        self.args = args

    def __get__(self, instance, owner):
        if not self.args:
            return self.get(instance)

        return functools.partial(self.get, self)

class E:
    def __init__(self, fn, ln):
        self.fn = fn
        self.ln = ln

    def full_name(self):
        return f'{self.ln}, {self.fn}'

    def w(self, q):
        return q * 10

    name    = T('name', full_name )
    weight  = T('weight', w, 10 )

if __name__ == '__main__':
    e = E('Sasha', 'Davidovich')

    print(e.name)
    print(e.weight(5))