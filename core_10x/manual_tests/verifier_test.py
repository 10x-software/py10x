from core_10x.traitable import RC, RC_TRUE, RT, Traitable


class Example(Traitable):
    code: str = RT()
    limit: int = RT(0)

    def code_verify(self, t, value: str) -> RC:
        """Run on verify() or save(); not on set."""
        if value and not value.isalnum():
            return RC(False, "code must be alphanumeric")
        return RC_TRUE

    def limit_verify(self, t, value: int) -> RC:
        if value is not None and value > 100:
            return RC(False, "limit must be <= 100")
        return RC_TRUE


if __name__ == "__main__":
    # Invalid values can be set; verification fails when requested
    e = Example()
    e.code = "invalid-code"
    e.limit = 150
    assert e.code == "invalid-code"
    assert e.limit == 150

    rc = e.verify()
    assert not rc  # fails due to code_verify and limit_verify

    # Fix and verify
    e.code = "valid"
    e.limit = 50
    e.verify().throw()  # success
