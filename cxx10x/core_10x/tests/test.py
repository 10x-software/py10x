import gc
from collections import Counter
from datetime import date
from typing import Any

import numpy as np
from core_10x.xnone import XNone
from core_10x.traitable import Traitable,T,RT,M,THIS_CLASS,AnonymousTraitable,RC
from core_10x.trait_method_error import TraitMethodError
from core_10x.code_samples.person import Person
from core_10x.exec_control import GRAPH_ON, GRAPH_OFF, CONVERT_VALUES_ON, DEBUG_ON, CACHE_ONLY,BTP, INTERACTIVE
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
        b:int = T()
        x:THIS_CLASS = T()

        @classmethod
        def exists_in_store(cls, id):
            raise RuntimeError()

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
        x1 = X(a=1,b=1,_force=True)
        x = X(ID("0"))
        print(x.a)
        #print(x,x,x,x.x.a)
        #assert x.x.a==1


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

def test_13():
    class X(Traitable):
        x:int = RT(T.ID)
        v:int = RT()

    X(x=1,v=10)
    assert X(x=1).v == 10

    default_cache = BTP.current().cache()
    with BTP.create(-1,-1,-1, use_parent_cache=False,use_default_cache=False) as btp0:
        #assert btp0.flags() & BTP.ON_GRAPH
        X(x=2,v=20)
        parent_cache = BTP.current().cache()
        assert default_cache is not parent_cache
        with BTP.create(-1,-1,-1, use_parent_cache=False,use_default_cache=False) as btp:
            #assert btp.flags() & BTP.ON_GRAPH
            X(x=3,v=30)
            child_cache = BTP.current().cache()
            assert child_cache is not parent_cache
            assert child_cache is not default_cache
            assert X(x=1).v == 10
            assert X(x=2).v == 20

        with BTP.create(-1,-1,-1,use_parent_cache=True,use_default_cache=False):
            X(x=4,v=40)
            child_cache = BTP.current().cache()
            assert child_cache is parent_cache
        with BTP.create(0,-1,-1,use_parent_cache=False,use_default_cache=True):
            X(x=5,v=50)
            child_cache = BTP.current().cache()
            assert child_cache is default_cache # use_default_cache only works for off-graph mode
            assert X(x=1).v == 10
            assert X(x=2).v is XNone

        assert X(x=1).v == 10 # from parent caches
        assert X(x=2).v == 20 # set in this cache
        assert X(x=3).v is XNone # not set as was set in child with use_parent_cache=False
        assert X(x=4).v == 40 # this cache, as was set in child with use_parent_cache=True
        assert X(x=5).v == 50 # in default cache, which is our parent

    assert X(x=1).v == 10
    assert X(x=2).v is XNone
    assert X(x=3).v is XNone
    assert X(x=4).v is XNone
    assert X(x=5).v == 50

    #TODO assert behavior with conflicting params

def test_14():
    class X(Traitable):
        x: int = RT(0)

    x = X()
    assert x.x == 0
    x.x = 1
    assert x.x == 1

    with BTraitableProcessor.create(on_graph=1,convert_values=-1,debug=-1,use_default_cache=False,use_parent_cache=False):
        with BTraitableProcessor.create(on_graph=-1,convert_values=-1,debug=-1,use_default_cache=False,use_parent_cache=False):
            assert x.x==1

    with BTraitableProcessor.create(on_graph=1,convert_values=-1,debug=-1,use_default_cache=False,use_parent_cache=False):
        assert x.x == 1
        # this node is not set and no valid, so falls back to parent
        with BTraitableProcessor.create(on_graph=-1,convert_values=-1,debug=-1,use_default_cache=False,use_parent_cache=False):
            assert x.x==1

    print('in', BTraitableProcessor.current().cache())

    with BTraitableProcessor.create(on_graph=1,convert_values=-1,debug=-1,use_default_cache=False,use_parent_cache=False):
        print('in', BTraitableProcessor.current().cache())
        x.invalidate_value('x')

        # this node is set and not valid, so works as white-out
        with BTraitableProcessor.create(on_graph=-1,convert_values=-1,debug=-1,use_default_cache=False,use_parent_cache=False):
            print('in', BTraitableProcessor.current().cache())
            assert x.x==0

def test_15():
    class X(Traitable):
        #s_custom_collection=True
        k:str = T(T.ID)
        v:int = T()
        v1:int = T(default=0)

        @classmethod
        def exists_in_store(cls, id):
            return int(id.value) < 4

        @classmethod
        def load_data(cls, id):
            print('load_data',id.value, BTraitableProcessor.current().cache())
            return {'_id':id.value,'k':id.value,'v':int(id.value)*10,'_rev':1}

    x1 = X.existing_instance(k='1')
    x2 = X.existing_instance(k='2')
    x3 = X.existing_instance(k='3')
    assert x1
    #assert x2
    #assert x3
    assert x1.v1==0
    x1.v1=1
    print('in', BTraitableProcessor.current().cache())
    with BTraitableProcessor.create(-1,-1,-1, use_parent_cache=False,use_default_cache=False):
        assert x1.v1==1
        x1.invalidate_value('v1')
        print('in', BTraitableProcessor.current().cache())
        with BTraitableProcessor.create(on_graph=1,convert_values=-1,debug=-1,use_default_cache=False,use_parent_cache=False):
            print('in', BTraitableProcessor.current().cache())
            assert x1.v==10
            assert x1.v1==0
            assert x2.v==20

    assert x1.v==10
    assert x2.v==20
    assert x3.v==30

def test_16():
    class X(Traitable):
        x: int = RT()
        #y: int = RT()
        z: int = RT()
        def z_get(self):
            return self.x + 1#self.y

    with GRAPH_ON() as g1:
        print('in', g1.cache())
        x = X(x=10,y=1)
        print('getting z')
        assert x.z == 11
        with GRAPH_ON() as g2:
            print('in', g2.cache())
            print('getting x')
            x.x = 20
            print('getting z')
            print(x.z)
            assert x.z == 21


def test_17():
    class X(Traitable):
        x: int = RT(T.ID)
        z: int = RT()

    x = X(x=1)
    x.z = 10

    try:
        X(x=1,z=1)
    except ValueError:
        pass
    else:
        assert False, "Expected ValueError as X is already created"

    x1 = X(x=1)
    assert x1.z == 10


def test_18():

    count = Counter()
    class X(Traitable):
        x: int = T(T.ID)
        y: int = T()

        @classmethod
        def exists_in_store(cls, id):
            return True

        @classmethod
        def load_data(cls, id):
            print('load_data', id.value)
            count[id.value] += 1
            return {'_id': id.value, 'x': int(id.value), 'y': int(id.value) * 10, '_rev': 1}


    x = X(ID('1')) # lazy ref

    # with GRAPH_ON():
    #     assert x.y == 10 # load
    #     assert count[x.id().value] == 1, count

    assert x.y == 10
    assert count[x.id().value] == 1

def test_19():
    class X(Traitable):
        x: int = RT(T.ID)
        y: int = RT(T.ID)
        z: int = RT()

        @classmethod
        def exists_in_store(self, id):
            raise RuntimeError()

    z = X(x=1, y=1, z=1,_force=True)
    with INTERACTIVE():
        x = X()  # empty object allowed - OK!
        assert z.z == 1

        x.x = 1
        x.y = 1
        #x.z = 2
        #assert x.z == 2

        assert not x.share(False)

def test_20():
    class X(Traitable):
        x: int = T(T.ID)
        y: int = T()

        @classmethod
        def exists_in_store(cls, id):
            return True

        def load_data(self):
            return {'_id':'1','_rev':1,'y':2}

    assert X.existing_instance(x=1, y=1).y == 2


def test_21():
    class X(Traitable):
        x: int = RT(T.ID)
        y: int = RT(T.ID_LIKE)
        z: int = RT(T.ID_LIKE)

        def x_get(self):
            return self.y + self.z

    assert X(y=1, z=1).x==2

    assert X(x=1).x==1

def test_22():
    class X(Traitable):
        x: int = T(T.ID)
        z: int = T()

        @classmethod
        def exists_in_store(cls, id):
            print('exists_in_store', id.value)
            return False

        @classmethod
        def load_data(cls, id):
            print('load_data', id.value)

    x = X(x=1)
    x.z = 1
    assert x.z == 1

    del x
    gc.collect()

    x = X(x=1)
    assert x.z == 1

def test_23():
    save_calls = Counter()

    class X(Traitable):
        x: int = T(T.ID)
        y: THIS_CLASS = T()

        def save(self, save_references=False):
            if self.serialize_object(save_references):
                save_calls[self.id().value] += 1
            return RC(True)

    x = X(x=1, y=X(x=2, y=X(x=1), _force=True), _force=True)
    x.save()
    assert save_calls == {'1': 1}
    save_calls.clear()

    x.save(save_references=True)
    assert save_calls == {'1': 1, '2': 1}
    save_calls.clear()

    x = X(x=1, y=X(_id=ID('3')), _force=True)
    x.save(save_references=True)
    assert save_calls == {'1': 1}  # save of a lazy load is noop

def test_24():
    class X(Traitable):
        x: int = RT(T.ID)

    x = X(x=1)
    assert x.x == 1
    try:
        x.x = 2
    except ValueError:
        pass
    else:
        assert False, "Expected ValueError on setting ID trait"

def test_25():
    rev = 0
    class X(Traitable):
        x: int = T(T.ID)

        @staticmethod
        def load_data(id):
            nonlocal rev
            rev += 1
            data = {'_id': id.value, 'x': int(id.value), '_rev': rev}
            print('load_data', id.value, data)
            return data

    # reload of lazy ref
    x = X(ID('1'))
    x.reload()
    assert x._rev == 1

    x.reload()
    assert x._rev == 2

    x = X(ID('2'))
    with GRAPH_ON():
        x.reload()
        assert x._rev == 3
        assert rev == 3

    assert x._rev == 3
    assert rev == 3

def test_26():
    class X(Traitable):
        x: int = T(T.ID)
        y: Any = T()

    with GRAPH_ON():
        x = X(x=1, y=np.float64(1.1), _force=True)
        s = x.serialize_object()
        print(s)

    with GRAPH_ON():
        assert s == X.deserialize_object(x.s_bclass, None, s).serialize_object()


def test_27():
    save_calls = Counter()
    serialized = {}

    class X(Traitable):
        x: int = T(T.ID)
        y: THIS_CLASS = T()
        z: int = T()

        @classmethod
        def exists_in_store(cls, id: ID) -> bool:
            return id.value in serialized or 100 > int(id.value) > 3

        @classmethod
        def load_data(cls, id: ID) -> dict | None:
            return serialized.get(id.value)


        @classmethod
        def collection(cls, _coll_name: str = None):
            class Collection:
                def save(self, serialized_data):
                    id_value = serialized_data['_id']
                    save_calls[id_value] += 1
                    serialized[id_value] = serialized_data

            return Collection()

        def y_get(self) -> 'X':
            i = int(self.id().value)
            return X(ID(str(i+10))) if i<10 else XNone

        def z_get(self)-> int:
           return self.y._rev if int(self.id().value) < 100 else 0

    x = X(x=100)
    assert X.serialize_object(x)
    assert not X.exists_in_store(ID('100'))
    assert x.save()
    assert save_calls == {'100': 1}
    serialized.clear()
    save_calls.clear()

    assert not serialized
    assert X(x=1,z=1,_force=True).save()
    assert save_calls == {'1': 1}
    assert serialized['1']['z'] == 1
    save_calls.clear()

    x = X(x=3, y=X(_id=ID('4')), _force=True)
    try:
        x.save(save_references=True)
    except Exception:
        pass
    else:
        assert False, "expected exception"
    assert save_calls == {}  # lazy load forced by z_get, cause exception as ID 4 does not exist
    save_calls.clear()

    X(x=5, y=X(_id=ID('6')), z=0, _force=True).save(save_references=True)
    assert save_calls == {'5': 1}  # save of a lazy load is noop

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
    # test_10()
    #test_12()
    #test_13()
    #test_14()
    #test_15()
    #test_16()
    #test_17()
    # test_18()
    # test_19()
    # test_20()
    #test_21()
    # test_22()
    # test_23()
    #test_24()
    # test_25()
    #test_26()
    test_27()


