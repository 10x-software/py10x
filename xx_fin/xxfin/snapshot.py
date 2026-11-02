from core_10x.named_constant import NamedConstant


class SNAPSHOT(NamedConstant):
    CLOSE   = ()
    MANUAL  = ()    ## manual overrides of mkt data, e.g., of a fixing; where overrides apply, looked up before the regular snapshot