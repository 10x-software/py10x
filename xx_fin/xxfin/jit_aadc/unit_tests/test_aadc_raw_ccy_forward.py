"""Hand-built AADC recording of ``CcyForward.price`` -- no ``AadcKernel`` involved.

Unit-test twin of ``manual_tests/aadc_raw_ccy_forward_test.py``: same GBP forward, same quotables,
but asserting rather than benchmarking. This is the reference the ``AadcKernel`` wrapper is
cross-checked against (see ``aadc_kernel_doc.md``), so it deliberately drives the raw
``mark_as_input`` / ``mark_as_output`` / ``evaluate_kernel`` API instead of the wrapper.

Market data comes entirely from the xxfin conftest fixtures -- the dev stores and the
``Abu Dhabi 20251010`` pricing context -- so nothing here hard-codes a quote.

Pricing here is straight-line arithmetic, so the recording is expected to be free of
active-to-passive conversions. ``test_aadc_monarch_butterfly.py`` is the deliberate counterexample.
"""

from datetime import date

import pytest
from core_10x.testlib.strict import need

from xxfin.ccy import Ccy
from xxfin.ccy_forward import CcyForward

try:
    #-- optional `aadc` extra (private index). Deferred to setup_method's need() so an
    #-- under-provisioned strict CI job fails loudly instead of collect-erroring here.
    from aadc import idouble
    from aadc.evaluate_wrappers import evaluate_kernel

    from xxfin.jit_aadc.aadc_context import AADCContext
    AADC_INSTALLED = True
except ImportError:
    AADC_INSTALLED = False

AADC_REASON = 'aadc not installed (py10x-fin-base[aadc] extra)'

#-- ~10Y past the fixture md_date (2025-10-10), so the 10Y swap quote carries most of the risk.
END_DATE = date(2035, 12, 12)

#-- AADC agrees with Python to ~1e-14 here. The loose adjoint bound is for the central-difference
#-- check, where the bump's own truncation error dominates (~1e-5 relative on the cash deposits).
PRICE_TOL   = 1e-12
FD_BUMP     = 1e-6
ADJOINT_REL = 1e-4
ADJOINT_ABS = 1e-9

class TestAadcRawCcyForward:
    def setup_method(self):
        need(AADC_INSTALLED, AADC_REASON)

        self.ccy_forward = CcyForward(denominated = Ccy('GBP'), end_date = END_DATE)
        self.py_price    = self.ccy_forward.price

        self.quotes = {}
        for quotables_by_date in ccy_forward.disc_curve.quotables_by_class.values():
            for quotable in quotables_by_date.values():
                self.quotes[quotable] = float(quotable.quote)

        for quotable, quote in quotes.items():
            quotable.quote = quote

        with AADCContext() as self.kernel:
            self.input_handles = {}
            for quotable, quote in quotes.items():
                active_quote = idouble(quote)
                quotable.quote = active_quote
                self.input_handles[quotable] = active_quote.mark_as_input()

            self.price_out = ccy_forward.price.mark_as_output()

        for quotable, quote in quotes.items():  # -- back to plain floats, off-kernel
            quotable.quote = quote

        self.inputs = { h: self.quotes[q] for q, h in self.input_handles.items() }

    def teardown_method(self):
        #-- test_isolation asserts no Traitable outlives the test; drop our references explicitly.
        self.ccy_forward = self.quotes = self.input_handles = self.inputs = None

    def _price(self, inputs = None) -> float:
        result = evaluate_kernel(self.kernel, {self.price_out: []}, inputs or self.inputs, 1)
        return result.values[self.price_out].item()

    def _price_and_adjoints(self) -> tuple[float, dict]:
        handles = list(self.input_handles.values())
        result  = evaluate_kernel(self.kernel, {self.price_out: handles}, self.inputs, 1)
        derivs  = result.derivs[self.price_out]
        return result.values[self.price_out].item(), { q: derivs[h].item() for q, h in self.input_handles.items() }

    def test_market_data_discovered(self):
        assert self.quotes, 'conftest fixtures produced a discount curve with no quotables'
        assert len(set(self.input_handles.values())) == len(self.quotes), 'one AADC input per quotable'

    def test_records_without_passive_warnings(self):
        """No branch, min/max or comparison on an active value, so the whole pricing path is
        differentiable as recorded -- nothing got frozen into the tape as a constant."""
        assert self.kernel.num_passive_warnings() == 0, \
            f'active-to-passive conversions recorded: {self.kernel.passive_warnings()}'

    def test_price_matches_python(self):
        assert self._price() == pytest.approx(self.py_price, abs = PRICE_TOL)

    def test_price_is_not_constant_in_the_quotes(self):
        """Guards the adjoint and reprice checks against a kernel that recorded a constant."""
        _, adjoints = self._price_and_adjoints()
        assert any(adj != 0. for adj in adjoints.values())

    def test_adjoints_match_finite_differences(self):
        _, adjoints = self._price_and_adjoints()

        for quotable, adjoint in adjoints.items():
            base = self.quotes[quotable]

            quotable.quote = base + FD_BUMP
            up = self.ccy_forward.price
            quotable.quote = base - FD_BUMP
            down = self.ccy_forward.price
            quotable.quote = base

            fd = (up - down) / (2 * FD_BUMP)
            assert adjoint == pytest.approx(fd, rel = ADJOINT_REL, abs = ADJOINT_ABS), \
                f'adjoint mismatch for {type(quotable).__name__} {quotable.tenor}'

    def test_kernel_reprices_bumped_market(self):
        """The recording is a real function of its inputs: replay it against a bumped quote and
        compare with a full Python reprice, no re-recording."""
        _, adjoints = self._price_and_adjoints()
        quotable    = max(adjoints, key = lambda q: abs(adjoints[q]))
        base        = self.quotes[quotable]
        bumped      = base + 1e-4

        kernel_price = self._price(self.inputs | {self.input_handles[quotable]: bumped})

        quotable.quote = bumped
        py_price = self.ccy_forward.price
        quotable.quote = base

        assert kernel_price == pytest.approx(py_price, abs = PRICE_TOL)
        assert kernel_price != pytest.approx(self.py_price, abs = PRICE_TOL), 'bump left the price unchanged'
