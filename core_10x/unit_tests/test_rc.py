from core_10x.rc import RC


def test_add():
    rc1 = RC(True)
    rc2 = RC(True)

    assert rc1 and rc2
    rc1 += rc2

    assert rc1 and rc2
