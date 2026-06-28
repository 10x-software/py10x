"""Pure release-batch planning for `xx-promote` (no git / filesystem I/O).

The design (`dev_10x/docs/rc-branch-promotion.md`, *Testing strategy*) calls for `_promote` to
compute a **plan** purely - which packages re-cut, at what version, with what coordinated pins, on
which branch, under what tag - separate from execution, so the combinatorial space can be asserted
exhaustively in-memory. This module is that planner; `xx_promote.py` gathers the git/pyproject
state into `PkgInput`s, calls `PrePlan`/`ProdPlan.create_batch`, then executes the returned `Plan`s.

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
from typing import TYPE_CHECKING, ClassVar

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
        # Footprint = the whole repo minus the *other* packages' subtrees (shared files count, a
        # sibling's subtree does not).
        latest = VersionHelpers.latest_tag(self.parsed_tags)
        if latest is None:
            return True
        fork = GitHelpers.git(self.repo, "merge-base", latest[0], "main")
        sibling_subdirs = [GitHelpers.repo_relative_subtree(self.repo, p.src_dir)
                           for n, p in self.packages.items() if n != self.name and p.repo == self.repo]
        return GitHelpers.tree_changed_since_tag(
            self.repo, fork, *GitHelpers.diff_pathspecs(*sibling_subdirs), rev="main")

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


def _coordinated_version(inp: PkgInput) -> tuple[str | None, bool]:
    """`pre`: (version, acts) by a package's own footprint - a new rc if changed, else its latest tag.

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


def _prod_target(inp: PkgInput) -> str | None:
    """`prod`: the version `inp` would finalize, or None when its latest tag is not a promotable rc."""
    latest = VersionHelpers.latest_tag(inp.parsed_tags)
    if latest is None or VersionHelpers.is_final(latest[1]):
        return None
    target = VersionHelpers.target_version(inp.parsed_tags)
    return target if VersionHelpers.latest_rc_tag(inp.parsed_tags, target) is not None else None


@dataclass(frozen=True)
class MainEdit:
    """A `main`-epilogue pyproject edit (rendered as a MainEditStep on the plan's own package)."""
    description: str
    forward_pins: dict[str, str] = field(default_factory=dict)
    test_pin: str | None = None


@dataclass(frozen=True)
class Plan:
    """One package's promote action - the **same shape** for `pre` (cut rc) and `prod` (stack final).

    `create_batch` is shared: it asks the subclass to **decide** each package's coordinated version
    (the only real pre/prod difference), then builds the coordinated cross-pins (core `==` siblings,
    each sibling `py10x-core>=` core) + the per-package plan + its `main` epilogue. Subclasses set
    `FLAVOR`/`BASE_KIND` and supply `_decide` (+ `_epilogue`/`_skip_reason`). One planner, two decisions.
    """
    name: str
    act: bool                                         # cut (pre) / promote (prod), vs skip
    version: str | None = None                        # coordinated version (rc for pre, final for prod)
    tag: str | None = None                            # f"{tag_prefix}{version}"
    branch: str | None = None                         # tool-owned release branch
    base_kind: str = "main"                           # PromoteStep forks from "main" HEAD or latest "rc"
    forward_pins: dict[str, str] = field(default_factory=dict)   # core: {sibling: "==ver"}
    reverse_pin: str | None = None                    # sibling: "py10x-core>=corever"
    epilogue: tuple = ()                              # MainEdit[] (main re-floor); empty for pre
    skip_reason: str | None = None

    FLAVOR: ClassVar[str]                             # "pre" | "prod"
    BASE_KIND: ClassVar[str]                          # "main" | "rc"

    @classmethod
    def create_batch(cls, inputs: list[PkgInput]) -> dict[str, Plan]:
        decided = cls._decide(inputs)                # {name: (coordinated version | None, acts)}
        core = next(i for i in inputs if i.is_core)
        siblings = [i for i in inputs if not i.is_core]
        plans: dict[str, Plan] = {}
        for inp in inputs:
            version, acts = decided[inp.name]
            if not acts:
                plans[inp.name] = cls(name=inp.name, act=False, skip_reason=cls._skip_reason(inp))
                continue
            if inp.is_core:
                forward = {s.name: VersionHelpers.exact_pin(decided[s.name][0])
                           for s in siblings if decided[s.name][0] is not None}
                reverse = None
            else:
                core_v = decided[core.name][0]
                forward = {}
                reverse = VersionHelpers.test_group_pin(core_v) if core_v is not None else None
            plans[inp.name] = cls(
                name=inp.name, act=True, version=version, tag=f"{inp.tag_prefix}{version}",
                branch=GitHelpers.release_branch(cls.FLAVOR, inp.name, inp.is_core),
                base_kind=cls.BASE_KIND, forward_pins=forward, reverse_pin=reverse,
                epilogue=cls._epilogue(inp, decided, inputs))
        return plans

    @classmethod
    def _decide(cls, inputs: list[PkgInput]) -> dict[str, tuple[str | None, bool]]:
        """{name: (coordinated version | None, acts)} - the per-flavor decision (abstract)."""
        raise NotImplementedError

    @classmethod
    def _epilogue(cls, inp: PkgInput, decided: dict, inputs: list[PkgInput]) -> tuple:
        return ()

    @classmethod
    def _skip_reason(cls, inp: PkgInput) -> str:
        raise NotImplementedError


class PrePlan(Plan):
    """`pre`: cut the next coordinated rc onto `pre`, forked from `main` HEAD (no `main` epilogue)."""
    FLAVOR = "pre"
    BASE_KIND = "main"

    @classmethod
    def _decide(cls, inputs):
        core = next(i for i in inputs if i.is_core)
        decided = {i.name: _coordinated_version(i) for i in inputs if not i.is_core}
        # core re-cuts on its own footprint OR a pin that lags any sibling's coordinated version.
        pin_lag = any(v is not None and core.current_forward.get(n) != v for n, (v, _) in decided.items())
        if core.footprint_changed or pin_lag:
            gen = core.generation_tags
            target = VersionHelpers.target_version(gen)
            decided[core.name] = (f"{target}rc{VersionHelpers.next_rc(gen, target)}", True)
        else:
            decided[core.name] = _coordinated_version(core)
        return decided

    @classmethod
    def _skip_reason(cls, inp):
        latest = VersionHelpers.latest_tag(inp.parsed_tags)
        return "no changes; never tagged" if latest is None else f"no changes since {latest[0]}"


class ProdPlan(Plan):
    """`prod`: stack the final on the latest rc onto `prod`, then re-floor `main` (the epilogue)."""
    FLAVOR = "prod"
    BASE_KIND = "rc"

    @classmethod
    def _decide(cls, inputs):
        return {i.name: ((t, True) if (t := _prod_target(i)) is not None else (None, False)) for i in inputs}

    @classmethod
    def _epilogue(cls, inp, decided, inputs):
        core_v = decided[next(i.name for i in inputs if i.is_core)][0]
        if inp.is_core:
            dev = {i.name: VersionHelpers.dev_pin(decided[i.name][0], VersionHelpers.next_micro(decided[i.name][0]))
                   for i in inputs if not i.is_core and decided[i.name][1]}
            return (MainEdit("bump sibling dev pins after prod promotion", forward_pins=dev),) if dev else ()
        return (MainEdit("track released py10x-core in test group",
                         test_pin=VersionHelpers.test_group_pin(core_v)),) if core_v is not None else ()

    @classmethod
    def _skip_reason(cls, inp):
        return "latest tag is not a pre-release with an rc"
