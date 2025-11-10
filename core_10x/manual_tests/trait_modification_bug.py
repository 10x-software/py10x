from core_10x.traitable import Traitable, RT, M

class A(Traitable):
    funny_message: str  = RT()

    def funny_message_get(self):
        dt = self.T.funny_message.data_type
        return f'{dt}'

class B(A):
    funny_message:int   = M()

class C(A):
    funny_message:float   = M()

    def funny_message_get(self):
        dt = self.T.funny_message.data_type
        return f'{dt}'

if __name__ == '__main__':
    a = A()
    b = B()
    c = C()

    print(f'A: {a.funny_message}; B: {b.funny_message}; C: {c.funny_message}')
