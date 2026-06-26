"""Plan-level tests for `dev_10x.xx_plan` (pure, in-memory, no git).

Asserts the declarative batch-formation rules across the combinatorial space: first-rc vs iterate,
changed vs unchanged package sets, the pin-lag trigger (a sibling re-cut, or a stale forward pin,
forces a core re-cut), and the prod promote/epilogue. `PrePlan`/`ProdPlan` share `Plan.create_batch`
and differ only in `_decide`/`_epilogue`. See `dev_10x/docs/rc-branch-promotion.md` (Batch formation).
"""
from __future__ import annotations

from dev_10x.xx_helpers import VersionHelpers
from dev_10x.xx_plan import PkgInput, PrePlan, ProdPlan

CORE, KERNEL, INFRA = "v", "py10x-kernel-v", "py10x-infra-v"


def _inp(name, is_core, prefix, tags, changed=False, current_forward=None, gen_tags=None):
    # PkgInput is a Traitable; setting the computed traits explicitly bypasses the (git) getters.
    parsed = VersionHelpers.parse_pkg_tags(tags, prefix)
    generation = (VersionHelpers.parse_pkg_tags(gen_tags, prefix, include_yanked=True)
                  if gen_tags is not None else parsed)
    return PkgInput(
        name=name, is_core=is_core, tag_prefix=prefix, parsed_tags=parsed,
        footprint_changed=changed, current_forward=current_forward or {}, generation_tags=generation,
    )


# ------------------------------------------------------------------------------- PrePlan.create_batch
def test_first_rc_for_all_packages_coordinates():
    """No tags anywhere, everything changed -> rc1 for each, cross-pinned to each other's rc1."""
    plans = PrePlan.create_batch([
        _inp("py10x-core", True, CORE, [], True),
        _inp("py10x-kernel", False, KERNEL, [], True),
        _inp("py10x-infra", False, INFRA, [], True),
    ])
    core = plans["py10x-core"]
    assert core.act and core.version == "0.0.1rc1" and core.tag == "v0.0.1rc1" and core.base_kind == "main"
    assert core.branch == "pre"
    assert core.forward_pins == {"py10x-kernel": "==0.0.1rc1", "py10x-infra": "==0.0.1rc1"}
    assert plans["py10x-kernel"].tag == "py10x-kernel-v0.0.1rc1"
    assert plans["py10x-kernel"].branch == "pre/py10x-kernel"
    assert plans["py10x-kernel"].reverse_pin == "py10x-core>=0.0.1rc1"
    assert plans["py10x-infra"].reverse_pin == "py10x-core>=0.0.1rc1"
    assert all(p.epilogue == () for p in plans.values())   # pre never touches main


def test_rc_iterate_bumps_next_rc_number():
    """Existing finals + rc's, everything changed again -> next micro, next rc number."""
    plans = PrePlan.create_batch([
        _inp("py10x-core", True, CORE, ["v0.2.0", "v0.2.1rc1"], True),
        _inp("py10x-kernel", False, KERNEL,
             [f"{KERNEL}1.4.0", f"{KERNEL}1.4.1rc1", f"{KERNEL}1.4.1rc2"], True),
        _inp("py10x-infra", False, INFRA, [f"{INFRA}0.9.0"], True),
    ])
    assert plans["py10x-core"].version == "0.2.1rc2"      # latest final 0.2.0 -> 0.2.1, rc1 -> rc2
    assert plans["py10x-kernel"].version == "1.4.1rc3"    # rc1/rc2 -> rc3
    assert plans["py10x-infra"].version == "0.9.1rc1"     # final 0.9.0 -> 0.9.1, first rc
    assert plans["py10x-core"].forward_pins == {
        "py10x-kernel": "==1.4.1rc3", "py10x-infra": "==0.9.1rc1"}
    assert plans["py10x-kernel"].reverse_pin == "py10x-core>=0.2.1rc2"


def test_changed_core_only_pins_unchanged_siblings_to_their_finals():
    """Only core's footprint changed; siblings unchanged -> core `==`-pins their latest finals, siblings skip."""
    plans = PrePlan.create_batch([
        _inp("py10x-core", True, CORE, ["v0.2.0"], True,
             current_forward={"py10x-kernel": "1.4.0", "py10x-infra": "0.9.0"}),
        _inp("py10x-kernel", False, KERNEL, [f"{KERNEL}1.4.0"], False),
        _inp("py10x-infra", False, INFRA, [f"{INFRA}0.9.0"], False),
    ])
    assert plans["py10x-core"].act
    assert plans["py10x-core"].forward_pins == {
        "py10x-kernel": "==1.4.0", "py10x-infra": "==0.9.0"}
    for s in ("py10x-kernel", "py10x-infra"):
        assert not plans[s].act
        assert plans[s].reverse_pin is None


def test_sibling_rc_forces_core_recut_even_if_core_unchanged():
    """A fresh kernel rc makes core's `==` pin stale -> core re-cuts despite no core footprint change."""
    plans = PrePlan.create_batch([
        _inp("py10x-core", True, CORE, ["v0.2.0", "v0.2.1rc1"], False,
             current_forward={"py10x-kernel": "1.4.0", "py10x-infra": "0.9.0"}),
        _inp("py10x-kernel", False, KERNEL, [f"{KERNEL}1.4.0"], True),   # changed -> new rc
        _inp("py10x-infra", False, INFRA, [f"{INFRA}0.9.0"], False),     # unchanged -> floors to final
    ])
    assert plans["py10x-kernel"].act and plans["py10x-kernel"].version == "1.4.1rc1"
    assert plans["py10x-core"].act                                       # forced by the pin lag
    assert plans["py10x-core"].version == "0.2.1rc2"
    assert plans["py10x-core"].forward_pins == {
        "py10x-kernel": "==1.4.1rc1", "py10x-infra": "==0.9.0"}
    assert plans["py10x-kernel"].reverse_pin == "py10x-core>=0.2.1rc2"
    assert not plans["py10x-infra"].act                                  # unchanged sibling stays put


def test_stale_forward_pin_alone_forces_core_recut():
    """No footprint changed anywhere, but core's pin trails the latest sibling final -> core re-cuts to refresh it."""
    plans = PrePlan.create_batch([
        _inp("py10x-core", True, CORE, ["v0.2.0"], False,
             current_forward={"py10x-kernel": "1.3.0"}),                 # lags the 1.4.0 final
        _inp("py10x-kernel", False, KERNEL, [f"{KERNEL}1.4.0"], False),
    ])
    assert plans["py10x-core"].act
    assert plans["py10x-core"].forward_pins == {"py10x-kernel": "==1.4.0"}
    assert not plans["py10x-kernel"].act


def test_unchanged_sibling_in_rc_phase_coordinates_to_its_rc():
    """Pre-1.0 (no finals yet): an unchanged sibling coordinates to its latest rc, never to a dropped pin."""
    plans = PrePlan.create_batch([
        _inp("py10x-core", True, CORE, ["v0.0.1rc1"], True,
             current_forward={"py10x-kernel": "0.0.1rc1"}),
        _inp("py10x-kernel", False, KERNEL, [f"{KERNEL}0.0.1rc1"], False),   # unchanged, only an rc
    ])
    assert plans["py10x-core"].version == "0.0.1rc2"
    assert plans["py10x-core"].forward_pins == {"py10x-kernel": "==0.0.1rc1"}
    assert not plans["py10x-kernel"].act


def test_nothing_changed_skips_all():
    """No footprint changes and pins in sync: every package skips (nothing to push - already on remote)."""
    plans = PrePlan.create_batch([
        _inp("py10x-core", True, CORE, ["v0.2.0", "v0.2.1rc2"], False,
             current_forward={"py10x-kernel": "1.4.0"}),
        _inp("py10x-kernel", False, KERNEL, [f"{KERNEL}1.4.0"], False),
    ])
    assert not plans["py10x-core"].act and plans["py10x-core"].skip_reason
    assert not plans["py10x-kernel"].act


def test_yanked_rc_number_is_consumed_not_reused():
    """A yanked rc number is consumed: generation floors above it, so the next cut is rc2, not rc1."""
    plans = PrePlan.create_batch([
        _inp("py10x-core", True, CORE, ["v0.2.0"], True,
             current_forward={"py10x-kernel": "0.2.0"}),
        # selection sees no live rc (rc1 was yanked); generation still counts the yanked rc1.
        _inp("py10x-kernel", False, KERNEL, [f"{KERNEL}0.2.0"], True,
             gen_tags=[f"{KERNEL}0.2.0", f"{KERNEL}0.2.1rc1_yanked"]),
    ])
    assert plans["py10x-kernel"].version == "0.2.1rc2"   # rc1 consumed, not reused


# ------------------------------------------------------------------------------ ProdPlan.create_batch
def test_prod_promotes_rcs_to_finals_and_coordinates():
    """Each package whose latest tag is an rc finalizes; core `==`-pins the released sibling finals."""
    plans = ProdPlan.create_batch([
        _inp("py10x-core", True, CORE, ["v0.2.0", "v0.2.1rc2"]),
        _inp("py10x-kernel", False, KERNEL, [f"{KERNEL}1.4.0", f"{KERNEL}1.4.1rc1"]),
        _inp("py10x-infra", False, INFRA, [f"{INFRA}0.9.0", f"{INFRA}0.9.1rc3"]),
    ])
    core = plans["py10x-core"]
    assert core.act and core.version == "0.2.1" and core.tag == "v0.2.1" and core.base_kind == "rc"
    assert core.branch == "prod"
    assert core.forward_pins == {"py10x-kernel": "==1.4.1", "py10x-infra": "==0.9.1"}
    # epilogue: core re-floors `main` dev pins to the released sibling versions
    assert core.epilogue[0].forward_pins["py10x-kernel"] == VersionHelpers.dev_pin("1.4.1", "1.4.2")
    assert plans["py10x-kernel"].tag == "py10x-kernel-v1.4.1"
    assert plans["py10x-kernel"].branch == "prod/py10x-kernel"
    assert plans["py10x-kernel"].reverse_pin == "py10x-core>=0.2.1"
    # epilogue: each released sibling points its `main` test group at the released core
    assert plans["py10x-kernel"].epilogue[0].test_pin == "py10x-core>=0.2.1"
    assert plans["py10x-infra"].version == "0.9.1" and plans["py10x-infra"].reverse_pin == "py10x-core>=0.2.1"


def test_prod_skips_packages_whose_latest_tag_is_final():
    """A package already on a final (nothing pre-release) is skipped; a promotable sibling still goes."""
    plans = ProdPlan.create_batch([
        _inp("py10x-core", True, CORE, ["v0.2.0"]),                       # latest is a final -> skip
        _inp("py10x-kernel", False, KERNEL, [f"{KERNEL}1.4.0", f"{KERNEL}1.4.1rc1"]),
    ])
    assert not plans["py10x-core"].act and plans["py10x-core"].skip_reason
    assert plans["py10x-kernel"].act and plans["py10x-kernel"].tag == "py10x-kernel-v1.4.1"
    # core not promoted -> no released core to point the sibling test group at
    assert plans["py10x-kernel"].reverse_pin is None and plans["py10x-kernel"].epilogue == ()


def test_prod_nothing_to_promote_skips_all():
    plans = ProdPlan.create_batch([
        _inp("py10x-core", True, CORE, ["v0.2.0"]),
        _inp("py10x-kernel", False, KERNEL, [f"{KERNEL}1.4.0"]),
    ])
    assert all(not p.act for p in plans.values())
