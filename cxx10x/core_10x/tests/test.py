import collections
from datetime import date

from core_10x.xnone import XNone
from core_10x.traitable import Traitable,T,RT,M,THIS_CLASS,AnonymousTraitable
from core_10x.trait_method_error import TraitMethodError
from core_10x.code_samples.person import Person
from core_10x.exec_control import GRAPH_ON, GRAPH_OFF, CONVERT_VALUES_ON, DEBUG_ON, CACHE_ONLY,BTP
from core_10x.ts_union import TsUnion

from core_10x.traitable_id import ID

from core_10x_i import BTraitableProcessor,XCache


def _test1():
    p = Person(first_name = 'Sasha', last_name = 'Davidovich')
    #p.weight_lbs = 100
    #assert p.weight == 100

    p.invalidate_value(p.T.weight)
    p.invalidate_value(p.T.weight_lbs)

    assert p.weight == XNone


def test_1():
    with TsUnion():
        with GRAPH_ON():
            _test1()
            with GRAPH_OFF():
                _test1()

def test_2():
    with TsUnion():
        p = Person(first_name = 'Sasha', last_name = 'Davidovich')
    with CONVERT_VALUES_ON():
        p.set_values(dob='December 1, 2000')
    age = (date.today().toordinal() - p.dob.toordinal())/365.25
    assert int(age) == p.age, f'Expected age around {int(age)}, got {p.age}'

def test_3():
    class X(Traitable):
        x:int = RT(T.ID)
        t:date = RT()
    p = X(x=1)
    p.t = XNone
    print(p.t)

    with DEBUG_ON():
        p.t = 'December 1, 2000'
    print(p.t)

    # with CONVERT_VALUES_ON():
    #     p.t = 1577836800
    # print(p.t)

def test_4():
    class X(Traitable):
        x:int = T(T.ID)

        @classmethod
        def x_serialize(cls,t,v):
            assert t is cls.trait(t.name)
            return f'{t.name}:{v}'

        @classmethod
        def x_deserialize(cls,t,v):
            assert t is cls.trait(t.name)
            return int(v.split(':')[-1])+1


    with TsUnion():
        p = X(x=1)
        s = p.serialize_object()
        print(p,s)
        p1 = X.deserialize_object(X.s_bclass,None,s)
        assert p == p1
        assert s['x']=='x:1'
        assert p.x==2

def test_5():
    from datetime import datetime,date
    class X(Traitable):
        x:int = T(T.ID)

    class Y(X):
        d:date = T(date.today())

    class Z(Traitable):
        y:Y = T(T.ID)
        t:datetime = T(datetime.now())

    with TsUnion():
        y = Y(x=1)
        print(y,y.serialize_object())
        y = Z(y=y)
        print(y,y.serialize_object())

def test_6():
    class X(Traitable):
        s_custom_collection=True
        x:int

    x=X(x=1,_collection_name='123')
    assert x.x==1

    XCache.clear()
    BTraitableProcessor.current().end_using()
    assert x.x is XNone

    x.x=1
    assert x.x==1


def test_7():
    class X(Traitable):
        s_custom_collection=True
        x:int = T(T.ID)
        y:int = T()

        def deserialize_traits(self,trait_values:dict):
            return super().deserialize_traits(trait_values|dict(y=trait_values['x']+1))

    with CACHE_ONLY():
        x=X(x=1,_collection_name='123')
        x = Traitable.deserialize_object(X.s_bclass,'123',dict(_rev=1,_id='1',x=1))
        assert x.x==1
        assert x.y==2

def test_8():
    class X(Traitable):
        k:int = T(T.ID)
        v:int = T()

        @classmethod
        def exists_in_store(cls, id):
            return True

        @classmethod
        def load_data(cls, id):
            print('load_data',id.value)
            return {'_id':id.value,'k':int(id.value),'v':int(id.value)*10,'_rev':1}

    class Y(X):
        c:X = T()

        @classmethod
        def load_data(cls, id):
            return super().load_data(id) | {'c': {'_id':str(int(id.value)+1)}}

    with BTP.create(1,1,1,True,True):
        x = Y(ID('1'))
        assert x.id().value == '1'
        assert x.k==1
        #assert x.v==10
        #assert x.c.v==20


def test_9():
    class X(Traitable):
        #s_custom_collection=True
        k:str = T(T.ID)
        v:int = T()

        @classmethod
        def exists_in_store(cls, id):
            return int(id.value) < 2

        @classmethod
        def load_data(cls, id):
            print('load_data',id.value)
            return {'_id':id.value,'k':id.value,'v':int(id.value)*10,'_rev':1}

    x1 = X.existing_instance(k='1')
    x2 = X.existing_instance(k='2',_throw=False)
    assert x1
    assert not x2

    assert x1.v==10


def test_10():
    class X(Traitable):
        a:int = T(T.ID)
        x:THIS_CLASS = T()

        @classmethod
        def exists_in_store(cls, id):
            return False

        @classmethod
        def load_data(cls, id):
            v = int(id.value)
            serialized_data = {'_id':id.value,'a':v,'_rev':1,'x': {'_id':str(int(not v))}}
            print('load_data',v, serialized_data)
            return serialized_data

        @classmethod
        def deserialize(cls,serialized_data:dict):
            print('deserialize',serialized_data)
            return super().deserialize(serialized_data)


    with  BTP.create(1,1,1,True,True):
        x = X(ID("0"))
        print(x,x,x,x.x.a)
        assert x.x.a==1


def test_11():
    class X(AnonymousTraitable):
        a:int = T()

        # @classmethod
        # def load_data(cls, id):
        #     return None

        # @classmethod
        # def exists_in_store(cls, id):
        #     return False

    class Y(Traitable):
        y:int = T(T.ID)
        x:Traitable = T()

        @classmethod
        def load_data(cls, id):
            return None

        @classmethod
        def exists_in_store(cls, id):
            return False

    class Z(Y):
        x:AnonymousTraitable = M(T.EMBEDDED)

    x = X(a=1)
    s = x.serialize(True)
    print(s)


    y = Y(y=0,x=x)
    try:
        y.serialize_object()
    except TraitMethodError as e:
        assert "test_11.<locals>.X - anonymous' instance may not be serialized as external reference" in str(e)
    else:
        assert False

    z = Z(y=1,x=x)
    s = z.serialize_object()
    print(s)
    assert s['x']['a']==1

    z = Z(y=2, x=Y(y=3))
    try:
        z.serialize_object()
    except TraitMethodError as e:
        assert "test_11.<locals>.Y/3 - embedded instance must be anonymous" in str(e)
    else:
        assert False


def test_12():
    class A(Traitable):
        s_default_trait_factory = T
        t: int

        @classmethod
        def exists_in_store(cls, id):
            return False

        @classmethod
        def load_data(cls, id):
            return None

    class B(A):
        def t_get(self):
            return 1
        @classmethod
        def t_serialize(cls, trait, value):
            return value + 1

    class C(B):
        t: str = M()

        def t_get(self):
            return 2

        @classmethod
        def t_serialize(cls, trait, value):
            return value + 2

    class D(C):
        t: date = M()

    for t, dt in zip([A, B, C, D], [int, int, str, date], strict=True):
        assert t.trait('t').data_type is dt

    for t, v in zip([A, B, C, D], [XNone, 1, 2, 2], strict=True):
        assert t().t is v
        assert t().serialize_object()['t'] == (v * 2 or None)

if __name__ == '__main__':
    import core_10x_i
    print(core_10x_i.__file__)
    #test_1()
    #test_2()
    #test_3()
    #test_4()
    #test_5()
    #test_6()
    #test_7()
    #test_8()
    #test_9()
    #test_10()
    test_12()



