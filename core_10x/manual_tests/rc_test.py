from core_10x.rc import RC, Enum, ErrorCode, RC_TRUE


class CONDITION(Enum):
    BEGIN   = ()
    MAIN    = ()
    END     = ()

class A_PROBLEM(ErrorCode):
    DOES_NOT_EXIST  = 'Entity {cls}.{id} does not exist'
    REV_CONFLICT    = 'Entity {cls}.{id} - revision {rev} is outdated'
    SAVE_FAILED     = 'Failed to save entity {cls}.{id}'

rc = RC_TRUE
print(rc)

try:
    rc.add_error('error')
    raise AssertionError('must have thrown')
except Exception as e:
    print(str(e))

rc = RC(CONDITION.MAIN, dict( a = 1, b = 1))
print(rc)

rc.add_data([100, 200])
print(rc)

rc1 = RC(False, 'just an error')
print(rc1)
try:
    rc1.throw()
except Exception as e:
    print(str(e))

rc = RC(A_PROBLEM.REV_CONFLICT, dict(cls = 'XXX', id = '123456', rev = 3))
print(rc)

rc = RC(True)
rc.add_error('First error')
rc.add_error(rc1)
print(rc)