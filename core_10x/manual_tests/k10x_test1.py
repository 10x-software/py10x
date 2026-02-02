from core_10x_i import NODE_TYPE, BasicNode

from core_10x.xnone import XNone  # -- keep

n1 = BasicNode.create(NODE_TYPE.BASIC_GRAPH)
n1.assign('whatever')

n2 = BasicNode.create(NODE_TYPE.BASIC_GRAPH)
n2.set(100)

n2.add_parent(n1)

n2.set('Asya')
