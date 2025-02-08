from core_10x.named_constant import EnumBits

class STATE(EnumBits):
    RESERVED    = ()
    RUNTIME     = ()
    ID          = ()

class XSTATE(STATE):
    EXPENSIVE   = ()

if __name__ == '__main__':
    r = STATE.RUNTIME | STATE.RESERVED | STATE.ID

    r2 = r - STATE.RESERVED

    e = XSTATE.EXPENSIVE