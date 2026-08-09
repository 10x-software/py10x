"""Pure, deterministic release planner for `xx-promote`.

The planner is the single source of truth for *what* a `pre` / `prod` run should do. The CLI
(`dev_10x.xx_promote`) is a thin executor: it gathers git / PyPI / working-tree state, packs that
state into `PkgInput`s, calls `PrePlan`/`ProdPlan.create_batch`, then executes the returned `Plan`s.
Nothing here shells out or mutates the filesystem - every decision is a pure function of the inputs,
so the combinatorial cases live in unit tests (`dev_10x/unit_tests/test_xx_plan.py`) and the CLI
owns I/O. See `dev_10x/README.md` (xx-promote) for the release model this encodes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

from core_10x.traitable import RT, T, Traitable

from dev_10x.xx_helpers import GitHelpers, PyProjectHelpers, VersionHelpers

if TYPE_CHECKING:
    from pathlib import Path


class PkgInput(Traitable):
    """Per-package state for the planner, derived from the package registry.

    In production the caller sets only `name` + `packages` (the `{name: Package}` registry); every
    other field is a **lazy getter** (the package's own attrs, or git reads, sticky-cached) - so a
    `PkgInput` decides for itself whether it is core / sibling / downstream. Tests set the computed
    traits explicitly, which bypasses the getters, keeping the planner unit-testable in-memory with
    no git.
    """

    name: str = RT()
    packages: dict = RT()  # the {name: Package} registry (sibling-aware context)
    tag_prefix: str = RT(T.STICKY)  # "v" for core, "py10x-kernel-v" for a sibling
    repo: Path = RT(T.STICKY)
    src_dir: Path = RT(T.STICKY)
    siblings: set = RT(T.STICKY)  # names this package forward-pins (published deps)
    is_core: bool = RT(T.STICKY)
    is_downstream: bool = RT(T.STICKY)
    parsed_tags: list = RT(T.STICKY)  # selection tags (yanked excluded)
    generation_tags: list = RT(T.STICKY)  # generation floor (yanked *included* - consumed)
    footprint_changed: bool = RT(T.STICKY)  # diff since the latest tag across diff_pathspecs
    current_forward: dict = RT(T.STICKY)  # exact == pins of `siblings` from latest tag
    version_override: str | None = RT(None)  # `--next-version`: forces a cut onto this X.Y.Z instead of next_micro

    def _pkg(self):
        return self.packages[self.name]

    def tag_prefix_get(self) -> str:
        return self._pkg().tag_prefix

    def repo_get(self) -> Path:
        return self._pkg().repo

    def src_dir_get(self) -> Path:
        return self._pkg().src_dir

    def is_core_get(self) -> bool:
        return self.tag_prefix == 'v'

    def is_downstream_get(self) -> bool:
        pkg = self.packages.get(self.name) if self.packages else None
        return bool(pkg and getattr(pkg, 'is_downstream', False))

    def siblings_get(self) -> set:
        # Forward-pin targets (published [project.dependencies]):
        #   core -> siblings only (never downstreams)
        #   downstream -> {core, optional co-released `{name}-cxx`}
        #   sibling -> empty
        if self.is_core:
            return {n for n, p in self.packages.items() if n != self.name and not p.is_core and not p.is_downstream}
        if self.is_downstream:
            return {n for n, p in self.packages.items() if p.is_core} | {f'{self.name}-cxx'}
        return set()

    def parsed_tags_get(self) -> list:
        return VersionHelpers.parse_pkg_tags(GitHelpers.list_tags(self.repo, f'{self.tag_prefix}*'), self.tag_prefix)

    def generation_tags_get(self) -> list:
        return VersionHelpers.parse_pkg_tags(GitHelpers.list_tags(self.repo, f'{self.tag_prefix}*'), self.tag_prefix, include_yanked=True)

    def footprint_changed_get(self) -> bool:
        # Diff from the main commit the latest tag was cut off (merge-base with main), not the tag
        # itself: the tag sits on the pre/prod line and carries pin commit(s), which aren't source.
        # Footprint = the whole repo minus the *other* packages' subtrees (shared files count, a
        # sibling's subtree does not). Skip excluding `.` (core's src_dir) so a nested downstream
        # still has a real footprint.
        latest = VersionHelpers.latest_tag(self.parsed_tags)
        if latest is None:
            return True
        fork = GitHelpers.git(self.repo, 'merge-base', latest[0], 'main')
        other_subdirs = [
            sub
            for n, p in self.packages.items()
            if n != self.name and p.repo == self.repo
            for sub in [GitHelpers.repo_relative_subtree(self.repo, p.src_dir)]
            if sub != '.'
        ]
        if not GitHelpers.tree_changed_since_tag(self.repo, fork, *GitHelpers.diff_pathspecs(*other_subdirs), rev='main'):
            return False
        # Pin-only exemption: core (sibling pins) and downstream (core + co-released *-cxx).
        if not self.siblings or not (self.is_core or self.is_downstream):
            return True
        rel = (self.src_dir / 'pyproject.toml').resolve().relative_to(self.repo.resolve()).as_posix()
        if GitHelpers.changed_files(self.repo, fork, rev='main') != [rel]:
            return True
        old = GitHelpers.file_at_ref(self.repo, fork, rel) or ''
        new = GitHelpers.file_at_ref(self.repo, 'main', rel) or ''
        return not PyProjectHelpers.diff_is_only_forward_pin_edits(old, new, self.siblings)

    def current_forward_get(self) -> dict:
        # Exact `==` pins of `siblings` (forward-pin targets) from the latest tag's pyproject.
        if not self.siblings:
            return {}
        parsed = VersionHelpers.parse_pkg_tags(GitHelpers.list_tags(self.repo, f'{self.tag_prefix}*'), self.tag_prefix)
        latest = VersionHelpers.latest_tag(parsed)
        if latest is None:
            return {}
        rel = (self.src_dir / 'pyproject.toml').resolve().relative_to(self.repo.resolve()).as_posix()
        text = GitHelpers.file_at_ref(self.repo, latest[0], rel)
        return PyProjectHelpers.exact_pins_from_text(text, self.siblings) if text else {}


def _next_rc_target(inp: PkgInput) -> str:
    """The base `X.Y.Z` a new rc cuts onto: `version_override` (`--next-version`) if set, else `next_micro`."""
    return VersionHelpers.base_version(inp.version_override) if inp.version_override else VersionHelpers.target_version(inp.generation_tags)


def _coordinated_version(inp: PkgInput) -> tuple[str | None, bool]:
    """`pre`: (version, acts) by a package's own footprint - a new rc if changed, else its latest tag.

    Unchanged -> the latest existing tag's version (rc or final), not a re-cut: that tag provably
    exists, so core's `==` pin onto it can never dangle, and during an rc cycle core stays
    coordinated with the in-flight rc rather than snapping back to an older final. The new-rc floor
    uses generation tags (so a yanked number is never reused); selection uses non-yanked tags.
    `version_override` (`--next-version`) forces a cut even when the footprint is unchanged, onto
    that target rather than the automatic next micro.
    """
    if inp.footprint_changed or inp.version_override:
        gen = inp.generation_tags
        target = _next_rc_target(inp)
        return f'{target}rc{VersionHelpers.next_rc(gen, target)}', True
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
    """A `main`-epilogue pyproject edit (rendered as a MainEditStep).

    `target` overrides which package receives the edit (default: the plan's own package). Used when
    a downstream cut must refresh core's unpublished test-group pin without re-cutting core.
    """

    description: str
    forward_pins: dict[str, str] = field(default_factory=dict)
    test_pin: str | list[str] | None = None
    target: str | None = None


@dataclass(frozen=True)
class Plan:
    """One package's promote action - the **same shape** for `pre` (cut rc) and `prod` (stack final).

    `create_batch` is shared: it asks the subclass to **decide** each package's coordinated version
    (the only real pre/prod difference), then builds the coordinated cross-pins (core `==` siblings,
    each sibling `py10x-core>=` core; downstream `==` core and co-released `{name}-cxx`) + the
    per-package plan + its `main` epilogue. Subclasses set `FLAVOR`/`BASE_KIND` and supply `_decide`
    (+ `_epilogue`/`_skip_reason`).
    """

    name: str
    act: bool  # cut (pre) / promote (prod), vs skip
    version: str | None = None  # coordinated version (rc for pre, final for prod)
    tag: str | None = None  # f"{tag_prefix}{version}"
    branch: str | None = None  # tool-owned release branch
    base_kind: str = 'main'  # PromoteStep forks from "main" HEAD or latest "rc"
    forward_pins: dict[str, str] = field(default_factory=dict)  # published [project.dependencies] pins
    reverse_pin: str | None = None  # sibling: "py10x-core>=corever" test-group
    epilogue: tuple = ()  # MainEdit[] (main pin refresh on core / siblings / downstreams)
    skip_reason: str | None = None

    FLAVOR: ClassVar[str]  # "pre" | "prod"
    BASE_KIND: ClassVar[str]  # "main" | "rc"

    @classmethod
    def create_batch(cls, inputs: list[PkgInput]) -> dict[str, Plan]:
        decided = cls._decide(inputs)  # {name: (coordinated version | None, acts)}
        core = next(i for i in inputs if i.is_core)
        siblings = [i for i in inputs if not i.is_core and not i.is_downstream]
        plans: dict[str, Plan] = {}
        for inp in inputs:
            version, acts = decided[inp.name]
            if not acts:
                plans[inp.name] = cls(name=inp.name, act=False, skip_reason=cls._skip_reason(inp))
                continue
            if inp.is_core:
                forward = {s.name: VersionHelpers.exact_pin(decided[s.name][0]) for s in siblings if decided[s.name][0] is not None}
                reverse = None
            elif inp.is_downstream:
                core_v = decided[core.name][0]
                forward = {core.name: VersionHelpers.exact_pin(core_v)} if core_v is not None else {}
                # Co-released impl dist (same tag train / version as the product package).
                # write_forward_pins only rewrites deps that already exist — no-op if absent.
                forward[f'{inp.name}-cxx'] = VersionHelpers.exact_pin(version)
                reverse = None
            else:
                core_v = decided[core.name][0]
                forward = {}
                reverse = VersionHelpers.test_group_pin(core_v) if core_v is not None else None
            plans[inp.name] = cls(
                name=inp.name,
                act=True,
                version=version,
                tag=f'{inp.tag_prefix}{version}',
                branch=GitHelpers.release_branch(cls.FLAVOR, inp.name, inp.is_core),
                base_kind=cls.BASE_KIND,
                forward_pins=forward,
                reverse_pin=reverse,
                epilogue=cls._epilogue(inp, decided, inputs),
            )
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


def _downstream_test_pins(decided: dict, inputs: list[PkgInput]) -> list[str]:
    """`dependency-groups.test` pins on core for each downstream with a coordinated version."""
    return [VersionHelpers.test_group_dep_pin(i.name, decided[i.name][0]) for i in inputs if i.is_downstream and decided[i.name][0] is not None]


class PrePlan(Plan):
    """`pre`: cut the next coordinated rc onto `pre`, forked from `main` HEAD; core `main` epilogue."""

    FLAVOR = 'pre'
    BASE_KIND = 'main'

    @classmethod
    def _epilogue(cls, inp, decided, inputs):
        core = next(i for i in inputs if i.is_core)
        if inp.is_core:
            edits: list[MainEdit] = []
            pins = {
                s.name: VersionHelpers.main_forward_window_pin(decided[s.name][0])
                for s in inputs
                if not s.is_core and not s.is_downstream and decided[s.name][0] is not None
            }
            if pins:
                edits.append(MainEdit('rc-window sibling pins on main', forward_pins=pins))
            ds_pins = _downstream_test_pins(decided, inputs)
            if ds_pins:
                edits.append(MainEdit('track downstreams in test group', test_pin=ds_pins))
            return tuple(edits)
        if inp.is_downstream:
            edits = []
            core_v = decided[core.name][0]
            fin_v = decided[inp.name][0]
            pins: dict[str, str] = {}
            if core_v is not None:
                pins[core.name] = VersionHelpers.main_forward_window_pin(core_v)
            if fin_v is not None:
                pins[f'{inp.name}-cxx'] = VersionHelpers.exact_pin(fin_v)
            if pins:
                edits.append(MainEdit('rc-window core + co-release cxx pins on main', forward_pins=pins))
            # Fin-base-only cut: refresh core's unpublished test-group pin without re-cutting core.
            if not decided[core.name][1] and fin_v is not None:
                edits.append(
                    MainEdit(
                        f'track {inp.name} in core test group',
                        test_pin=VersionHelpers.test_group_dep_pin(inp.name, fin_v),
                        target=core.name,
                    )
                )
            return tuple(edits)
        return ()

    @classmethod
    def _decide(cls, inputs):
        core = next(i for i in inputs if i.is_core)
        siblings = [i for i in inputs if not i.is_core and not i.is_downstream]
        downstreams = [i for i in inputs if i.is_downstream]
        decided = {i.name: _coordinated_version(i) for i in siblings}
        # core re-cuts on its own footprint, an explicit --next-version, OR a pin that lags any
        # *sibling*'s coordinated version.
        pin_lag = any(v is not None and core.current_forward.get(n) != v for n, (v, _) in decided.items())
        if core.footprint_changed or core.version_override or pin_lag:
            gen = core.generation_tags
            target = _next_rc_target(core)
            decided[core.name] = (f'{target}rc{VersionHelpers.next_rc(gen, target)}', True)
        else:
            decided[core.name] = _coordinated_version(core)
        # downstreams: own footprint, an explicit --next-version, OR published core pin lag vs this
        # batch's coordinated core.
        core_v = decided[core.name][0]
        for d in downstreams:
            if d.footprint_changed or d.version_override or (core_v is not None and d.current_forward.get(core.name) != core_v):
                gen = d.generation_tags
                target = _next_rc_target(d)
                decided[d.name] = (f'{target}rc{VersionHelpers.next_rc(gen, target)}', True)
            else:
                decided[d.name] = _coordinated_version(d)
        return decided

    @classmethod
    def _skip_reason(cls, inp):
        latest = VersionHelpers.latest_tag(inp.parsed_tags)
        return 'no changes; never tagged' if latest is None else f'no changes since {latest[0]}'


class ProdPlan(Plan):
    """`prod`: stack the final on the latest rc onto `prod`, then re-floor `main` (the epilogue)."""

    FLAVOR = 'prod'
    BASE_KIND = 'rc'

    @classmethod
    def _decide(cls, inputs):
        return {i.name: ((t, True) if (t := _prod_target(i)) is not None else (None, False)) for i in inputs}

    @classmethod
    def _epilogue(cls, inp, decided, inputs):
        core = next(i for i in inputs if i.is_core)
        core_v = decided[core.name][0]
        if inp.is_core:
            edits: list[MainEdit] = []
            dev = {
                i.name: VersionHelpers.post_final_window_pin(decided[i.name][0])
                for i in inputs
                if not i.is_core and not i.is_downstream and decided[i.name][1]
            }
            if dev:
                edits.append(MainEdit('post-final window sibling pins on main', forward_pins=dev))
            ds_pins = _downstream_test_pins(decided, inputs)
            if ds_pins:
                edits.append(MainEdit('track downstreams in test group', test_pin=ds_pins))
            return tuple(edits)
        if inp.is_downstream:
            edits = []
            fin_v = decided[inp.name][0]
            pins: dict[str, str] = {}
            if core_v is not None:
                pins[core.name] = VersionHelpers.post_final_window_pin(core_v)
            if fin_v is not None:
                pins[f'{inp.name}-cxx'] = VersionHelpers.exact_pin(fin_v)
            if pins:
                edits.append(MainEdit('post-final core + co-release cxx pins on main', forward_pins=pins))
            if not decided[core.name][1] and fin_v is not None:
                edits.append(
                    MainEdit(
                        f'track {inp.name} in core test group',
                        test_pin=VersionHelpers.test_group_dep_pin(inp.name, fin_v),
                        target=core.name,
                    )
                )
            return tuple(edits)
        return (MainEdit('track released py10x-core in test group', test_pin=VersionHelpers.test_group_pin(core_v)),) if core_v is not None else ()

    @classmethod
    def _skip_reason(cls, inp):
        return 'latest tag is not a pre-release with an rc'
