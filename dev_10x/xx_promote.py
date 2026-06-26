"""`xx-promote` - release promotion for the three 10x packages.

The three packages version *independently* and live in two git repos:

    py10x-core   -> repo `py10x`   (this repo),     tags  `vX.Y.Z[rcN]`
    py10x-kernel -> repo `cxx10x`/core_10x,         tags  `py10x-kernel-vX.Y.Z[rcN]`
    py10x-infra  -> repo `cxx10x`/infra_10x,        tags  `py10x-infra-vX.Y.Z[rcN]`

`main` carries *dev* pins (prerelease-admitting) that admit a sibling's next pre-release without
`--prerelease=allow`; releases are cut by tagging and (for prod) committing strict pins on a
per-version release branch. See `dev_10x/README.md` for the full model.

It is a `core_10x.traitable_cli.TraitableCli` tree: positional words pick the command, and
options use the `--option value` form (dashes in names map to underscores; boolean options also
accept the `--option` / `--no-option` shortcuts).

Subcommands:
    xx-promote pre                                  cut the next rc when the package tree changed
    xx-promote prod                                 promote packages whose latest tag is a pre-release
    xx-promote yank --pkg <name> --version <ver>    rename a tag to `<tag>_yanked`; roll back main pins
    xx-promote status                               show pending promotions (tagged but not on PyPI)

Safety levels (every subcommand), as `--option` flags:
    (default)        perform local changes only (git log/status to inspect, reset to undo)
    --dry-run        print the full plan, change nothing (local or remote)
    --push           perform local changes, then push to remotes last

`dry_run` always wins over `push`. Example: `xx-promote prod --dry-run`.
"""
from __future__ import annotations

from pathlib import Path

import tomlkit
from packaging.version import Version

from core_10x.rc import exc_to_rc
from core_10x.trait_definition import RT
from core_10x.traitable import RC, RC_TRUE, T, Traitable
from core_10x.traitable_cli import TraitableCli
from dev_10x.xx_plan import Plan, PrePlan, ProdPlan, PkgInput
from dev_10x.xx_helpers import (
    GhUnavailableError,
    GitHelpers,
    GitHubHelpers,
    PyProjectHelpers,
    PyPIHelpers,
    VersionHelpers,
)


class Package(Traitable):
    name: str          # distribution name, e.g. "py10x-kernel"
    src_dir: Path

    repo: Path         # git repo root
    tag_prefix: str    # tag namespace, e.g. "py10x-kernel-v" (core is just "v")
    pyproject: Path    # path to the package's pyproject.toml

    def repo_get(self) -> Path: return GitHelpers.git_root(self.src_dir)
    def tag_prefix_get(self) -> str: return f'{self.name}-v'
    def pyproject_get(self) -> Path: return self.src_dir / 'pyproject.toml'


# --------------------------------------------------------------------------------------------
# Steps - one side-effecting action each. Subclasses hold the declarative inputs as traits and put
# the value logic in *sticky* getters (`summary`, `push_refs`, computed once); `apply()` performs
# the mutation. `run_steps` applies every step, then pushes (remotes last).
# --------------------------------------------------------------------------------------------
class Step(Traitable):
    summary: str = RT(T.STICKY)
    push_refs: tuple = RT(T.STICKY)

    def push_refs_get(self) -> tuple:
        return ()                       # default: a local-only step touches no remote

    def apply(self) -> None:
        """Perform the side effect. Default no-op (e.g. a skip or a printed notice)."""


class PkgStep(Step):
    """A step acting on one package; exposes its repo + core-ness as sticky getters."""
    pkg: Package = RT()
    repo: Path = RT(T.STICKY)
    is_core: bool = RT(T.STICKY)

    def repo_get(self) -> Path:
        return self.pkg.repo

    def is_core_get(self) -> bool:
        return self.pkg.tag_prefix == "v"


class PromoteStep(PkgStep):
    """One package's promote action - the **same execution** for `pre` (cut rc) and `prod` (stack
    final), so every rc dress-rehearses the prod path. Writes the plan's coordinated pins on `base`
    (`main` HEAD for pre, the latest rc commit for prod), force-updates the release branch, tags.
    """
    plan: Plan = RT()
    base: str = RT(T.STICKY)            # commit the release branch forks from (only when acting)

    def base_get(self) -> str:
        if self.plan.base_kind == "rc":          # prod stacks the final on the latest rc commit
            parsed = VersionHelpers.parse_pkg_tags(
                GitHelpers.list_tags(self.repo, f"{self.pkg.tag_prefix}*"), self.pkg.tag_prefix)
            return GitHelpers.tag_commit(self.repo, VersionHelpers.latest_rc_tag(parsed, self.plan.version))
        return GitHelpers.git(self.repo, "rev-parse", "main")   # pre forks from main HEAD

    def summary_get(self) -> str:
        plan = self.plan
        if not plan.act:
            return f"{self.pkg.name}: {plan.skip_reason} - skip"
        pins = {**plan.forward_pins}
        if plan.reverse_pin:
            pins["test"] = plan.reverse_pin
        verb = "promote" if plan.base_kind == "rc" else "cut"
        return f"{self.pkg.name}: {verb} {plan.tag} on {plan.branch} off {self.base[:10]} with pins {pins}"

    def push_refs_get(self) -> tuple:
        return (self.repo, [f"+{self.plan.branch}", self.plan.tag]) if self.plan.act else ()

    def apply(self) -> None:
        plan = self.plan
        if not plan.act:
            return
        GitHelpers.git(self.repo, "checkout", "-q", "-B", plan.branch, self.base)
        if plan.forward_pins or plan.reverse_pin:
            if plan.forward_pins:
                PyProjectHelpers.write_forward_pins(self.pkg.pyproject, plan.forward_pins)
            if plan.reverse_pin:
                PyProjectHelpers.write_test_group(self.pkg.pyproject, plan.reverse_pin)
            # --allow-empty: a re-cut whose pins didn't change still puts a commit on the branch.
            GitHelpers.git(self.repo, "commit", "-aqm", f"promote: {plan.tag}", "--allow-empty")
            GitHelpers.git(self.repo, "tag", plan.tag)
        else:
            GitHelpers.git(self.repo, "tag", plan.tag)   # no pin delta: released == base verbatim
        GitHelpers.git(self.repo, "checkout", "-q", "main")


class MainEditStep(PkgStep):
    """A `main`-epilogue edit: checkout main, write `forward_pins` and/or a `test_pin` group on the
    package's pyproject, commit, push `main`. The edit is data (no subclasses); `description` labels
    both the dry-run summary and the commit message.
    """
    forward_pins: dict = RT()           # {dep: spec} for [project.dependencies]
    test_pin: str | None = RT()         # py10x-core pin for the `test` group
    description: str = RT()

    def forward_pins_get(self) -> dict:
        return {}

    def test_pin_get(self) -> str | None:
        return None

    def summary_get(self) -> str:
        return f"main: {self.pkg.name} {self.description}"

    def push_refs_get(self) -> tuple:
        return (self.repo, ["main"])

    def apply(self) -> None:
        GitHelpers.git(self.repo, "checkout", "main")
        if self.forward_pins:
            PyProjectHelpers.write_forward_pins(self.pkg.pyproject, self.forward_pins)
        if self.test_pin:
            PyProjectHelpers.write_test_group(self.pkg.pyproject, self.test_pin)
        GitHelpers.git(self.repo, "commit", "-am", self.description)


class YankTagStep(Step):
    """yank: rename a tag to `<tag>_yanked` (and delete the original), pushing both refs."""
    repo: Path = RT()
    tag: str = RT()
    yanked: str = RT(T.STICKY)

    def yanked_get(self) -> str:
        return f"{self.tag}_yanked"

    def summary_get(self) -> str:
        return f"rename tag {self.tag} -> {self.yanked}"

    def push_refs_get(self) -> tuple:
        return (self.repo, [self.yanked, f":refs/tags/{self.tag}"])

    def apply(self) -> None:
        GitHelpers.git(self.repo, "tag", self.yanked, self.tag)
        GitHelpers.git(self.repo, "tag", "-d", self.tag)


class RollbackStep(Step):
    """yank: force the affected `pre`/`prod` pointer back to the previous tag of the same kind."""
    repo: Path = RT()
    branch: str = RT()
    to_tag: str = RT()
    to_commit: str = RT()

    def summary_get(self) -> str:
        return f"roll {self.branch} back to {self.to_tag}"

    def push_refs_get(self) -> tuple:
        return (self.repo, [f"+{self.branch}"])

    def apply(self) -> None:
        GitHelpers.git(self.repo, "branch", "-f", self.branch, self.to_commit)


class NoticeStep(Step):
    """A printed-only step (no git mutation, no push) - e.g. the manual PyPI yank instructions."""
    message: str = RT()

    def summary_get(self) -> str:
        return self.message


class ResetRepoStep(Step):
    """reset-local: force one repo's managed refs (main + pre/prod branches + tags) to match origin.

    Discards local-only work and resyncs to the consistent remote (a no-op when there is no origin).
    """
    repo: Path = RT()
    branches: list = RT()               # managed branch names: main + the pre/prod release branches
    tag_globs: list = RT()

    def summary_get(self) -> str:
        others = ", ".join(b for b in self.branches if b != "main")
        return f"reset-local {self.repo}: main, {others} + tags := origin"

    def apply(self) -> None:
        repo = self.repo
        if not GitHelpers.has_origin(repo):
            return
        GitHelpers.git(repo, "fetch", "--prune", "origin")
        for branch in self.branches:
            remote = GitHelpers.ls_remote_ref(repo, f"refs/heads/{branch}")
            if branch == "main":
                if remote is not None:
                    GitHelpers.git(repo, "checkout", "-q", "-f", "main")
                    GitHelpers.git(repo, "reset", "--hard", remote)
            elif remote is None:
                GitHelpers.git(repo, "branch", "-D", branch, check=False)   # local-only -> drop
            else:
                GitHelpers.git(repo, "branch", "-f", branch, remote)
        for glob in self.tag_globs:
            local, remote = set(GitHelpers.list_tags(repo, glob)), GitHelpers.ls_remote_tags(repo, glob)
            for t in sorted(local - remote):
                GitHelpers.git(repo, "tag", "-d", t)
            for t in sorted(remote - local):
                GitHelpers.git(repo, "fetch", "-q", "origin", "tag", t)


# --------------------------------------------------------------------------------------------
# CLI surface - a core_10x.traitable_cli tree. Commands are positional; options are --option value.
# --------------------------------------------------------------------------------------------
class XxPromote(TraitableCli):
    """Release promotion for the 10x packages.

    Usage:
        xx-promote pre                                cut the next rc when the package tree changed
        xx-promote prod                               promote packages whose latest tag is pre
        xx-promote yank --pkg <name> --version <ver>  yank a tag (rc or final)
        xx-promote status                             list tagged-but-unpublished versions + CI state
        xx-promote resync                             recovery: force local managed refs to origin
    Flags: --dry-run (preview), --push (push to remotes). --base <path> overrides the py10x repo
    root (default: cwd). Boolean flags also accept the explicit `--flag true|false` form.
    """
    dry_run: bool = RT(False)   # traitable_cli coerces the CLI string ("true"/"1") to a real bool
    push: bool = RT(False)
    base: str = RT(".")

    packages: dict[str, Package] = RT(T.STICKY)
    steps: list[Step] = RT(T.STICKY)
    inputs: list[PkgInput] = RT(T.STICKY)

    def packages_get(self) -> dict[str, Package]:
        """Build the package registry from `[tool.dev_10x.siblings]` in `base/pyproject.toml`.

        Sibling repo roots are discovered via `git rev-parse --show-toplevel`; tag prefixes follow
        the naming convention `{name}-v` unless overridden by a `tag_prefix` key in the inline table.
        """
        base = Path(self.base).resolve()
        doc = tomlkit.parse((base / "pyproject.toml").read_text(encoding="utf-8"))
        core_name = str(doc["project"]["name"])
        siblings = doc.get("tool", {}).get("dev_10x", {}).get("siblings", {})
        result = {
            name: Package(name=name, src_dir=(base / spec["path"]).resolve()) for name, spec in siblings.items()
        }
        result[core_name] = Package(name=core_name, src_dir=base, tag_prefix='v')
        return result

    def inputs_get(self) -> list[PkgInput]:
        """The planners' PkgInputs - each gets the registry and derives the rest via its getters."""
        return [PkgInput(name=name, packages=self.packages) for name in self.packages]

    def _promote_steps(self, plan_cls: type[Plan]) -> list[Step]:
        """The one shared pre/prod routine: a PromoteStep per package (cut or stack, per `plan_cls`)
        plus each plan's `main` epilogue. Flavors differ only in `plan_cls` - same execution path."""
        pkgs = self.packages
        plans = plan_cls.create_batch(self.inputs)
        steps: list[Step] = [PromoteStep(pkg=pkg, plan=plans[name]) for name, pkg in pkgs.items()]
        steps += [MainEditStep(pkg=pkgs[name], forward_pins=e.forward_pins, test_pin=e.test_pin,
                               description=e.description)
                  for name, plan in plans.items() for e in plan.epilogue]
        return steps

    @exc_to_rc
    def run_steps(self) -> None:
        # `steps` is T.STICKY, computed once (applying mutates the git state steps_get reads). Apply
        # every local step first; then push each repo ONCE, **atomically** (all-or-nothing) and last,
        # so a crash never leaves a repo's remote half-updated - recovery is `reset-local` + re-run.
        for s in self.steps:
            print(('  [dry-run] ' if self.dry_run else '  ') + s.summary)
            if not self.dry_run:
                s.apply()
        if self.dry_run:
            return
        if not self.push:
            print('\nLocal changes applied. Review with `git log`/`git status`; re-run with push=true to publish.')
            return
        by_repo: dict[Path, list[str]] = {}
        for s in self.steps:
            if s.push_refs:
                repo, refspecs = s.push_refs
                by_repo.setdefault(repo, []).extend(refspecs)
        for repo, refspecs in by_repo.items():
            refspecs = list(dict.fromkeys(refspecs))   # dedup, preserve order (e.g. two `main` edits)
            print(f"  push --atomic {refspecs} -> {repo}")
            GitHelpers.git(repo, "push", "--atomic", "origin", *refspecs)

    @exc_to_rc
    def post_verify(self) -> None:
        repo_globs: dict[Path, list[str]] = {}
        for p in self.packages.values():
            repo_globs.setdefault(p.repo, []).append(f'{p.tag_prefix}*')
        for repo, globs in repo_globs.items():
            GitHelpers.require_synced(repo, globs)

        assert next(reversed(self.packages.values())).tag_prefix == 'v'  # -- siblings before core

    def run(self) -> RC:
        if not self.steps:
            # bare `xx-promote` with no command -> usage (full docstring)
            return RC(False, self.__doc__)
        rc = self.verify()
        if not rc:
            return rc
        if title := (self.__doc__ or "").strip().splitlines():
            print(title[0])                            # just the one-line title, not the whole docstring
        return self.run_steps()


class Pre(XxPromote, _command="pre"):
    """xx-promote pre  (cut the next coordinated rc onto the tool-owned `pre` branch).

    For every package the planner re-cuts (`PrePlan.create_batch`), write the coordinated pins -
    core's exact forward `==` on its siblings, each sibling's reverse `py10x-core>=` test group - on a
    commit forked from `main` HEAD, force-reset the package's `pre` branch to it, and tag `v{T}rcN`.
    Unchanged packages are skipped. See `dev_10x/docs/rc-branch-promotion.md`.
    """

    def post_verify(self) -> RC:
        return RC_TRUE if self.dry_run else super().post_verify()

    def steps_get(self) -> list[Step]:
        return self._promote_steps(PrePlan)


class Prod(XxPromote, _command="prod"):
    """xx-promote prod  (stack the final on the latest rc; force-update the `prod` branch).

    Promotes each package whose latest tag is a pre-release (`ProdPlan.create_batch`): stacks a
    final-pin commit on the rc commit (so released source == rc source), force-updates `prod`, tags
    `v{T}` (forward pins become exact `==T`; reverse `test` group `py10x-core>=T`), and the plan's
    `main` epilogue re-floors the dev pins to the released versions. See `…/rc-branch-promotion.md`.
    """

    def steps_get(self) -> list[Step]:
        return self._promote_steps(ProdPlan)


class Yank(XxPromote, _command="yank"):
    """xx-promote yank  (yank the latest tag - rc or final - and roll the pre/prod pointer back)."""
    pkg: str = T(T.NOT_EMPTY)           # distribution name (the --pkg arg)
    version: str = T(T.NOT_EMPTY)

    # Shared, sticky-cached derivations used by both post_verify and steps_get.
    package: Package = RT(T.STICKY)     # the resolved Package for `pkg`
    tag: str = RT(T.STICKY)             # the tag being yanked, f"{tag_prefix}{version}"
    parsed: list = RT(T.STICKY)         # the package's parsed tags (yanked excluded)
    is_prod: bool = RT(T.STICKY)        # final (prod) vs rc (pre) yank
    core: Package = RT(T.STICKY)        # the core package (for the sibling-final dev-pin rollback)

    def package_get(self) -> Package:
        return self.packages[self.pkg]

    def tag_get(self) -> str:
        return f'{self.package.tag_prefix}{self.version}'

    def parsed_get(self) -> list:
        return VersionHelpers.parse_pkg_tags(
            GitHelpers.list_tags(self.package.repo, f'{self.package.tag_prefix}*'), self.package.tag_prefix)

    def is_prod_get(self) -> bool:
        return VersionHelpers.is_final_version_string(self.version)

    def core_get(self) -> Package:
        return next(p for p in self.packages.values() if p.tag_prefix == "v")

    @exc_to_rc
    def post_verify(self) -> None:
        """Preconditions (run by verify() before run(); exc_to_rc -> RC): known package + tag, synced, latest-only."""
        super().post_verify().throw()
        if self.pkg not in self.packages:
            raise RuntimeError(f'unknown package {self.pkg!r}; choose from {", ".join(self.packages)}')
        if not GitHelpers.list_tags(self.package.repo, self.tag):
            raise RuntimeError(f'tag {self.tag!r} not found in {self.package.repo}')
        if not self.dry_run:
            GitHelpers.require_synced(self.package.repo, [f'{self.package.tag_prefix}*'])
        # Stage 1 yanks the latest release only (an older one would orphan everything after it and
        # needs `--cascade`, Stage 2). The tag-found check above guarantees `latest` is not None.
        latest = VersionHelpers.latest_tag(self.parsed)
        if latest is None or Version(self.version) != latest[1]:
            raise RuntimeError(f'{self.tag} is not the latest tag ({latest[0] if latest else "none"}); '
                               f'yanking an older release needs --cascade (Stage 2, not yet available)')

    def steps_get(self) -> list[Step]:
        repo = self.package.repo
        print(f'xx-promote yank {self.pkg} {self.version}  ({"prod" if self.is_prod else "pre"})\n')
        steps: list[Step] = [YankTagStep(repo=repo, tag=self.tag)]

        # Roll the affected pointer back to the previous tag of the same kind (rc -> pre, final ->
        # prod), pushed so a --push yank finishes local==remote. Computed at plan time (the previous
        # tag is known); the generic reconcile can't see this move since the rename happens at apply.
        remaining = [(t, v) for t, v in self.parsed if v != Version(self.version)]
        prev_tag = (VersionHelpers.latest_final_tag(remaining) if self.is_prod
                    else VersionHelpers.latest_rc_tag_overall(remaining))
        if prev_tag is not None:
            branch = GitHelpers.release_branch(
                "prod" if self.is_prod else "pre", self.pkg, self.package.tag_prefix == "v")
            steps.append(RollbackStep(repo=repo, branch=branch, to_tag=prev_tag,
                                      to_commit=GitHelpers.tag_commit(repo, prev_tag)))

        if self.is_prod and self.package.tag_prefix != "v":
            # Yanking a sibling final: it disappears from selection, so core's main dev pin must
            # re-floor to the latest non-yanked release (`remaining` already excludes the yanked one).
            lf = VersionHelpers.latest_final(remaining)
            floor = VersionHelpers.base_version(lf) if lf is not None else "0.0.0"
            steps.append(MainEditStep(
                pkg=self.core,
                forward_pins={self.pkg: VersionHelpers.dev_pin(floor, VersionHelpers.next_micro(floor))},
                description=f"roll back {self.pkg} dev pin after yanking v{self.version}"))

        # The index yank itself is manual: PyPI has no public yank API (a session-authenticated web
        # action), so there is no CI workflow for it - we just print what to do.
        manage_url = f'https://pypi.org/manage/project/{self.pkg}/release/{self.version}/'
        steps.append(NoticeStep(message=(
            f'MANUAL: PyPI has no yank API - yank {self.pkg} {self.version} on the index yourself:\n'
            f'      {manage_url}  (Options -> Yank)')))
        return steps


class Status(XxPromote, _command="status"):
    """xx-promote status  (pending promotions: tags pushed but the version isn't on PyPI yet)

    For each package it compares local tags (rc + final, yanked tags excluded) against PyPI and
    reports tags pushed since the latest PyPI release that are not on the index yet. For each
    pending tag it resolves the publish workflow run and reports its state and a link. Read-only:
    no git or remote mutation, ignores --dry-run / --push.
    """

    def post_verify(self) -> RC:
        return RC_TRUE   # read-only report - never require_synced

    def _pending(self, name: str, pkg: Package) -> list[tuple[str, Version]]:
        """Tags for `pkg` pushed since the latest PyPI release and not yet on the index."""
        parsed = VersionHelpers.parse_pkg_tags(
            GitHelpers.list_tags(pkg.repo, f"{pkg.tag_prefix}*"), pkg.tag_prefix)
        published = PyPIHelpers.published_versions(name)
        return VersionHelpers.pending_promotions(parsed, published)

    @staticmethod
    def _runs(slug: str, cache: dict[str, list[dict]], errors: dict[str, str]) -> list[dict]:
        """`gh` push runs for `slug`, fetched once per repo; gh errors degrade to an empty list."""
        if slug not in cache:
            try:
                cache[slug] = GitHubHelpers.push_runs(slug)
            except GhUnavailableError as e:
                errors[slug] = str(e)
                cache[slug] = []
        return cache[slug]

    def run(self) -> RC:
        rc = self.verify()
        if not rc:
            return rc
        print("xx-promote status  (tagged but not yet published on PyPI)\n")
        runs_cache: dict[str, list[dict]] = {}
        gh_errors: dict[str, str] = {}
        any_pending = False
        for name, pkg in self.packages.items():
            slug = GitHubHelpers.remote_slug(pkg.repo)
            runs = self._runs(slug, runs_cache, gh_errors)
            pending = self._pending(name, pkg)
            if not pending:
                print(f"  {name}: up to date - nothing pending since the latest PyPI release.")
                continue
            any_pending = True
            print(f"  {name}:")
            for tag, _ver in pending:
                run = GitHubHelpers.select_run_for_tag(runs, tag)
                state = "unknown (gh unavailable)" if run is None and slug in gh_errors \
                    else GitHubHelpers.run_state(run)
                url = run.get("html_url", "") if run else ""
                print(f"      {tag}  workflow: {state}{('  ' + url) if url else ''}")
        if not any_pending:
            print("\nNothing pending since the latest PyPI release.")
        for slug, err in gh_errors.items():
            print(f"\nnote: workflow state for {slug} is unavailable: {err}")
        return RC_TRUE


class Resync(XxPromote, _command="resync"):
    """xx-promote resync  (recovery: discard local work, force managed refs to match origin).

    After a crash, `require_synced` refuses the next promote until local == remote (atomic pushes keep
    the remote consistent, so it is the source of truth). This resyncs each repo - fetch origin, then
    force `main`/`pre`/`prod` branches and the managed tags to their origin counterpart, deleting
    local-only ones - so you can re-run cleanly. Destructive; preview with --dry-run. No-op without an
    `origin`. (CLI command words must be identifiers, so this is `resync`, not `reset-local`.)
    """

    def post_verify(self) -> RC:
        return RC_TRUE   # recovery runs *because* local != remote - never require_synced here

    def steps_get(self) -> list[Step]:
        repo_branches: dict[Path, set[str]] = {}
        repo_globs: dict[Path, list[str]] = {}
        for name, pkg in self.packages.items():
            is_core = pkg.tag_prefix == "v"
            repo_branches.setdefault(pkg.repo, {"main"}).update(
                (GitHelpers.release_branch("pre", name, is_core),
                 GitHelpers.release_branch("prod", name, is_core)))
            repo_globs.setdefault(pkg.repo, []).append(f"{pkg.tag_prefix}*")
        return [ResetRepoStep(repo=repo, branches=sorted(repo_branches[repo]), tag_globs=repo_globs[repo])
                for repo in repo_branches]


def main() -> int:
    rc, inst = XxPromote.from_command_line()
    if not rc:
        print(rc.error())
        return 2
    rc = inst.run()
    if not rc:
        print(rc.error())
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
