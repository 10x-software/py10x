from core_10x.traitable import Traitable, T, RT

class Book(Traitable):
    name: str       = T(T.ID)
    anything: bool  = T()

if __name__ == '__main__':
    from core_10x.manual_tests.existing_instance_bug import Book

    b1 = Book(name = 'B1')
    b2 = Book(_replace = True, name = 'B2', anything = False)

    try:
        b11 = Book.existing_instance(name = 'B1')
    except ValueError as ex:
        print(str(ex))

    b21 = Book.existing_instance(name = 'B2')

