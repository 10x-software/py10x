"""Pure release-batch planning for `xx-promote` (no git / filesystem I/O).

The design (`dev_10x/docs/rc-branch-promotion.md`, *Testing strategy*) calls for `_promote` to
compute a **plan** purely - which packages re-cut, at what version, with what coordinated pins, on
which branch, under what tag - separate from execution, so the combinatorial space can be asserted
exhaustively in-memory. This module is that planner; `xx_promote.py` gathers the git/pyproject
state into `PkgInput`s, calls `plan_pre_batch`, then executes the returned `PkgPlan`s.

Stage 1 covers `pre --from=main` (cut the next coordinated rc). Batch formation is **declarative**
(decisions compare persistent state - tags + current pins - never an in-process diff):

- **sibling:** re-cut iff its own footprint changed since its last tag.
- **core:** re-cut iff its own footprint changed **or** its current forward `==` pin lags a
  sibling's coordinated version (so a fresh sibling rc forces a core re-cut to refresh the pin).

An **unchanged** package is not re-cut; its coordinated version floors to its latest **final**
(the "unchanged sibling" rule), which is what core then `==`-pins.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core_10x.trait_definition import RT
from core_10x.traitable import T, Traitable
from dev_10x.xx_helpers import GitHelpers, PyProjectHelpers, VersionHelpers

if TYPE_CHECKING:
    from pathlib import Path


class PkgInput(Traitable):
    """Per-package state for the planner, derived from the package registry.

    In production the caller sets only `name` + `packages` (the `{name: Package}` registry); every
    other field is a **lazy getter** (the package's own attrs, or git reads, sticky-cached) - so a
    `PkgInput` decides for itself whether it is core (has siblings to forward-pin) or a sibling.
    Tests set the computed traits explicitly, which bypasses the getters, keeping the planner
    unit-testable in-memory with no git.
    """
    name: str = RT()
    packages: dict = RT()                             # the {name: Package} registry (sibling-aware context)
    tag_prefix: str = RT(T.STICKY)                    # "v" for core, "py10x-kernel-v" for a sibling
    repo: Path = RT(T.STICKY)
    src_dir: Path = RT(T.STICKY)
    siblings: set = RT(T.STICKY)                      # names this package forward-pins (only core's is non-empty)
    is_core: bool = RT(T.STICKY)
    parsed_tags: list = RT(T.STICKY)                  # selection tags (yanked excluded)
    generation_tags: list = RT(T.STICKY)              # generation floor (yanked *included* - consumed)
    footprint_changed: bool = RT(T.STICKY)            # diff since the latest tag across diff_pathspecs
    current_forward: dict = RT(T.STICKY)              # core only: {sibling: version currently ==-pinned}

    def _pkg(self):
        return self.packages[self.name]

    def tag_prefix_get(self) -> str:
        return self._pkg().tag_prefix

    def repo_get(self) -> Path:
        return self._pkg().repo

    def src_dir_get(self) -> Path:
        return self._pkg().src_dir

    def is_core_get(self) -> bool:
        return self.tag_prefix == "v"

    def siblings_get(self) -> set:
        # core forward-pins every other package; a sibling forward-pins nothing.
        return {n for n in self.packages if n != self.name} if self.is_core else set()

    def parsed_tags_get(self) -> list:
        return VersionHelpers.parse_pkg_tags(
            GitHelpers.list_tags(self.repo, f"{self.tag_prefix}*"), self.tag_prefix)

    def generation_tags_get(self) -> list:
        return VersionHelpers.parse_pkg_tags(
            GitHelpers.list_tags(self.repo, f"{self.tag_prefix}*"), self.tag_prefix, include_yanked=True)

    def footprint_changed_get(self) -> bool:
        # Diff from the main commit the latest tag was cut off (merge-base with main), not the tag
        # itself: the tag sits on the pre/prod line and carries pin commit(s), which aren't source.
        latest = VersionHelpers.latest_tag(self.parsed_tags)
        if latest is None:
            return True
        fork = GitHelpers.git(self.repo, "merge-base", latest[0], "main")
        return GitHelpers.tree_changed_since_tag(
            self.repo, fork, *GitHelpers.diff_pathspecs(self.repo, self.src_dir), rev="main")

    def current_forward_get(self) -> dict:
        # core's published forward `==` pins, read from its latest tag's pyproject and filtered to
        # the sibling names. A sibling (empty `siblings`) tracks no forward pins.
        if not self.siblings:
            return {}
        parsed = VersionHelpers.parse_pkg_tags(
            GitHelpers.list_tags(self.repo, f"{self.tag_prefix}*"), self.tag_prefix)
        latest = VersionHelpers.latest_tag(parsed)
        if latest is None:
            return {}
        rel = (self.src_dir / "pyproject.toml").resolve().relative_to(self.repo.resolve()).as_posix()
        text = GitHelpers.file_at_ref(self.repo, latest[0], rel)
        return PyProjectHelpers.exact_pins_from_text(text, self.siblings) if text else {}


@dataclass(frozen=True)
class PkgPlan:
    """The planned action for one package in a `pre` batch."""
    name: str
    recut: bool
    version: str | None = None                        # coordinated version, e.g. "0.2.1rc3"
    tag: str | None = None                            # f"{tag_prefix}{version}"
    branch: str | None = None                         # tool-owned `pre` branch (release_branch)
    forward_pins: dict[str, str] = field(default_factory=dict)   # core: {sibling: "==ver"}
    reverse_test_pin: str | None = None               # sibling: "py10x-core>=corever"
    skip_reason: str | None = None


def _coordinated_version(inp: PkgInput) -> tuple[str | None, bool]:
    """(version, recut) by a package's own footprint: a new rc if changed, else its latest tag.

    Unchanged -> the latest existing tag's version (rc or final), not a re-cut: that tag provably
    exists, so core's `==` pin onto it can never dangle, and during an rc cycle core stays
    coordinated with the in-flight rc rather than snapping back to an older final. The new-rc floor
    uses generation tags (so a yanked number is never reused); selection uses non-yanked tags.
    """
    if inp.footprint_changed:
        gen = inp.generation_tags
        target = VersionHelpers.target_version(gen)
        return f"{target}rc{VersionHelpers.next_rc(gen, target)}", True
    latest = VersionHelpers.latest_tag(inp.parsed_tags)
    return (str(latest[1]) if latest is not None else None), False


def _skip_plan(inp: PkgInput) -> PkgPlan:
    """No re-cut. (The latest tag is already on the remote - the `local==remote` start invariant -
    so there is nothing to push; a stale local-only tag would have failed `require_synced`.)"""
    latest = VersionHelpers.latest_tag(inp.parsed_tags)
    reason = "no changes; never tagged" if latest is None else f"no changes since {latest[0]}"
    return PkgPlan(name=inp.name, recut=False, skip_reason=reason)


def plan_pre_batch(inputs: list[PkgInput]) -> dict[str, PkgPlan]:
    """Plan a `pre --from=main` batch. Returns {package name: PkgPlan}.

    Coordination is two-pass (siblings first, so core can `==`-pin a version that already exists):
    each sibling's coordinated version is decided by its own footprint; core then re-cuts if its
    footprint changed or any sibling's coordinated version differs from its current `==` pin, and
    pins each sibling `==` that version; every re-cut sibling pins `py10x-core>=` core's version.
    """
    core = next(i for i in inputs if i.is_core)
    siblings = [i for i in inputs if not i.is_core]

    coord: dict[str, str | None] = {}
    recut: dict[str, bool] = {}

    # Pass 1 - siblings, by their own footprint.
    for s in siblings:
        coord[s.name], recut[s.name] = _coordinated_version(s)

    # Pass 2 - core re-cuts on its own footprint OR a pin that lags any sibling's coordinated version.
    pin_lag = any(coord[s.name] is not None and core.current_forward.get(s.name) != coord[s.name]
                  for s in siblings)
    if core.footprint_changed or pin_lag:
        gen = core.generation_tags
        target = VersionHelpers.target_version(gen)
        coord[core.name] = f"{target}rc{VersionHelpers.next_rc(gen, target)}"
        recut[core.name] = True
    else:
        coord[core.name], recut[core.name] = _coordinated_version(core)

    plans: dict[str, PkgPlan] = {}

    # core: forward `==` pins to each sibling's coordinated version.
    if recut[core.name]:
        forward = {s.name: VersionHelpers.exact_pin(coord[s.name])
                   for s in siblings if coord[s.name] is not None}
        plans[core.name] = PkgPlan(
            name=core.name, recut=True, version=coord[core.name],
            tag=f"{core.tag_prefix}{coord[core.name]}",
            branch=GitHelpers.release_branch("pre", core.name, core.is_core),
            forward_pins=forward,
        )
    else:
        plans[core.name] = _skip_plan(core)

    # siblings: each re-cut sibling pins `py10x-core>=` core's coordinated version.
    core_v = coord[core.name]
    for s in siblings:
        if recut[s.name]:
            plans[s.name] = PkgPlan(
                name=s.name, recut=True, version=coord[s.name],
                tag=f"{s.tag_prefix}{coord[s.name]}",
                branch=GitHelpers.release_branch("pre", s.name, s.is_core),
                reverse_test_pin=(VersionHelpers.test_group_pin(core_v) if core_v is not None else None),
            )
        else:
            plans[s.name] = _skip_plan(s)

    return plans


@dataclass(frozen=True)
class ProdPlan:
    """The planned action for one package in a `prod` batch."""
    name: str
    promote: bool
    target: str | None = None                         # the finalized version, e.g. "0.2.1"
    tag: str | None = None                            # f"{tag_prefix}{target}"
    branch: str | None = None                         # tool-owned `prod` branch
    forward_pins: dict[str, str] = field(default_factory=dict)   # core: {sibling: "==target"}
    test_pin: str | None = None                       # sibling: "py10x-core>=core_target"
    dev_pins: dict[str, str] = field(default_factory=dict)       # core main-epilogue: {sibling: dev_pin}
    skip_reason: str | None = None


def _prod_target(inp: PkgInput) -> str | None:
    """The version `inp` would finalize, or None when its latest tag is not a promotable rc."""
    latest = VersionHelpers.latest_tag(inp.parsed_tags)
    if latest is None or VersionHelpers.is_final(latest[1]):
        return None
    target = VersionHelpers.target_version(inp.parsed_tags)
    return target if VersionHelpers.latest_rc_tag(inp.parsed_tags, target) is not None else None


def plan_prod_batch(inputs: list[PkgInput]) -> dict[str, ProdPlan]:
    """Plan a `prod` batch: promote each package whose latest tag is an rc to its final.

    Mirrors `plan_pre_batch` (pure, coordinated): core `==`-pins the released sibling versions and
    re-floors its `main` dev pins to them; each released sibling pins `py10x-core>=` the released core.
    """
    core = next(i for i in inputs if i.is_core)
    targets = {i.name: t for i in inputs if (t := _prod_target(i)) is not None}
    core_t = targets.get(core.name)
    sib_final = {n: VersionHelpers.exact_pin(t) for n, t in targets.items() if n != core.name}
    sib_dev = {n: VersionHelpers.dev_pin(t, VersionHelpers.next_micro(t))
               for n, t in targets.items() if n != core.name}

    plans: dict[str, ProdPlan] = {}
    for inp in inputs:
        if inp.name not in targets:
            plans[inp.name] = ProdPlan(name=inp.name, promote=False,
                                       skip_reason="latest tag is not a pre-release with an rc")
            continue
        t = targets[inp.name]
        plans[inp.name] = ProdPlan(
            name=inp.name, promote=True, target=t,
            tag=f"{inp.tag_prefix}{t}",
            branch=GitHelpers.release_branch("prod", inp.name, inp.is_core),
            forward_pins=(sib_final if inp.is_core else {}),
            test_pin=(VersionHelpers.test_group_pin(core_t) if not inp.is_core and core_t else None),
            dev_pins=(sib_dev if inp.is_core else {}),
        )
    return plans
