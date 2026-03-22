from core_10x.basket import Basket, Bucketizer
from core_10x.code_samples.person import Person
from core_10x.xinf import XInf
from core_10x.named_constant import NamedCallable

class FEATURE(NamedCallable):
    A60     = lambda p: p.older_than(60)
    W200    = lambda p: p.weight >= 200

if __name__ == '__main__':

    all_people = Person.load_many()

    class AGGREGATOR(NamedCallable):
        WEIGHT     = lambda gen: sum(v*q for v, q in gen)

    b = Basket(base_class = Person, aggregator_class = AGGREGATOR)

    #bz = Bucketizer.by_feature(Person, FEATURE.W200)
    #bz = Bucketizer.by_breakpoints(Person, lambda p: p.weight, -XInf, 100, 170, 200, XInf)
    #bz = Bucketizer.by_range(Person, Person.T.weight, ('underweight', -XInf, 100), ('normal', 170., 180.), ['overweight', 190., XInf])
    #bz = Bucketizer.by_feature(Person, lambda p: p.weight, 190., 200.)

    bz = Bucketizer.by_range(Person, Person.T.weight, ('underweight', -XInf, 100), ('normal', 170., 180.), ['overweight', 190., XInf])
    bz2 = Bucketizer.by_feature(Person, Person.T.age)

    b.bucketizers = [bz, bz2]
    for i, p in enumerate(all_people):
        b.add(p, i)

    for tag, bucket in b.tags_buckets():
        print(f'tag = {tag}:')
        for member, qty in bucket.members_qtys():
            print(f'{member} = {qty}')

    r = b.weight
    print(f'weight = {r}')

    b.bucketizers = []
    for i, p in enumerate(all_people[:-1]):
        b.add(p, i)

    r = b.weight
    print(f'weight = {r}')

    bz = Bucketizer.by_range(Person, Person.T.age, ('normal', 50, XInf ))
    b.add_bucketizer(bz)

    r = b.weight
    print(f'weight = {r}')


    bz = Bucketizer.by_range(Person, Person.T.weight, ('underweight', -XInf, 100), ('normal', 170., 180.), ['overweight', 190., XInf])
    b.bucketizers = [bz]
    for i, p in enumerate(all_people):
        b.add(p, i)

    print('*** by subtags ***')
    # for tag, bucket in b.tags_buckets():
    #     print(f'tag = {tag}: {bucket.data}')
    gen = b.buckets_by_subtags('overweight')
    for tag, bucket in gen:
        print(f'tag = {tag}:')
        print(bucket.data)
