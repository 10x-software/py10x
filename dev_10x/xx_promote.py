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
    xx-promote pre --no-publish                     cut without creating publish triggers
    xx-promote pre --publish-only                   push publish triggers for the latest rc tags
    xx-promote prod                                 promote packages whose latest tag is a pre-release
    xx-promote prod --publish-only                  push publish triggers for the latest finals
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
from core_10x.trait_definition import RT, M
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
    is_core: bool = RT(T.STICKY)

    repo: Path = RT(T.STICKY)   # git repo root - STICKY: `git_root` is immutable, don't re-shell per access
    tag_prefix: str = RT(T.STICKY)    # tag namespace, e.g. "py10x-kernel-v" (core is just "v")
    pyproject: Path = RT(T.STICKY)   # path to the package's pyproject.toml

    def repo_get(self) -> Path: return GitHelpers.git_root(self.src_dir)
    def tag_prefix_get(self) -> str: return 'v' if self.is_core else f'{self.name}-v'
    def pyproject_get(self) -> Path: return self.src_dir / 'pyproject.toml'


# --------------------------------------------------------------------------------------------
# Steps - one side-effecting action each. Subclasses hold the declarative inputs as traits and put
# the value logic in *sticky* getters (`summary`, `tags_to_push`, …); `apply()` performs the
# mutation. `run_steps` applies every step, then pushes (remotes last).
# --------------------------------------------------------------------------------------------
class Step(Traitable):
    summary: str = RT(T.STICKY)
    tags_to_push: tuple = RT(T.STICKY)
    isolated_tags_to_push: tuple = RT(T.STICKY)
    is_mutator: bool = RT(True)

    def apply(self) -> None:
        """Perform the side effect. Default no-op (e.g. a skip or a printed notice)."""

class PkgStep(Step):
    """A step acting on one package; exposes its repo + core-ness as sticky getters."""
    pkg: Package = RT()
    repo: Path = RT(T.STICKY)

    def repo_get(self) -> Path:
        return self.pkg.repo


class PromoteStep(PkgStep):
    """One package's promote action - the **same execution** for `pre` (cut rc) and `prod` (stack
    final), so every rc dress-rehearses the prod path. Writes the plan's coordinated pins on `base`
    (`main` HEAD for pre, the latest rc commit for prod), force-updates the release branch, tags.
    """
    plan: Plan = RT()
    base: str = RT(T.STICKY)

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

    def tags_to_push_get(self) -> tuple:
        if not self.plan.act:
            return ()
        return (self.repo, [f"+{self.plan.branch}", self.plan.tag])

    def is_mutator_get(self) -> bool:
        return self.plan.act

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


class TagReplaceStep(PkgStep):
    """Delete stale auxiliary tags and create one new tag on a chosen commit."""
    tag: str | None = RT(T.STICKY)
    stale_tags: list = RT(T.STICKY)
    tag_force: bool = RT(T.STICKY)
    tag_commit: str = RT(T.STICKY|T.NOT_EMPTY)
    summary_prefix: str = RT(T.NOT_EMPTY)

    def tag_force_get(self) -> bool:
        return False

    def summary_get(self) -> str:
        drop = f", drop {self.stale_tags}" if self.stale_tags else ""
        return f"{self.pkg.name}: {self.summary_prefix} {self.tag}{drop}"

    def is_mutator_get(self) -> bool:
        return bool(self.tag)

    def apply(self) -> None:
        if not self.tag:
            return
        commit = self.tag_commit_get()
        if not commit:
            return
        for t in self.stale_tags:
            if t != self.tag:
                GitHelpers.git(self.repo, "tag", "-d", t, check=False)
        args = ["tag"]
        if self.tag_force:
            args.append("-f")
        GitHelpers.git(self.repo, *args, self.tag, commit)


class MainDevMarkerStep(TagReplaceStep):
    """Retag `main` HEAD with the setuptools-scm dev marker (after promote steps + main epilogue).

    `pre` sets `{T}rc(N+1).dev`; `prod` replaces rc-line markers with `{next_micro(T)}rc0.dev` so
    `main` stays strictly above the published final.
    """
    plan: Plan = RT()

    def tag_get(self) -> str | None:
        plan = self.plan
        if not plan.act or not plan.tag:
            return None
        prefix = self.pkg.tag_prefix
        if plan.base_kind == "main":
            return VersionHelpers.main_dev_marker_tag(plan.tag, prefix)
        return VersionHelpers.main_post_final_dev_marker_tag(plan.tag, prefix)

    def stale_tags_get(self) -> list[str]:
        if not self.tag:
            return []
        return VersionHelpers.existing_main_dev_marker_tags(
            GitHelpers.list_tags(self.repo, f"{self.pkg.tag_prefix}*"), self.pkg.tag_prefix)

    def tag_commit_get(self) -> str:
        # Read-only: getters must never mutate (this one is evaluated on the dry-run/verify path).
        # `apply()` tags this commit explicitly, so no checkout is needed.
        return GitHelpers.git(self.repo, "rev-parse", "main")

    def tag_force_get(self) -> bool:
        return True

    def tags_to_push_get(self) -> tuple:
        if not self.tag:
            return ()
        refs = [f":refs/tags/{t}" for t in self.stale_tags if t != self.tag]
        refs.append(self.tag)
        return (self.repo, refs)

    def summary_prefix_get(self) -> str:
        return "tag main"


class PublishTriggerStep(TagReplaceStep):
    """Tag the release commit with `pre/{release}` or `prod/{release}` to trigger publish CI.

    Publish-trigger refspecs go in `isolated_tags_to_push` (one `git push` each) so CI always
    gets tag-create webhooks. With `create_only=True` (`--publish-only`), stale triggers are not deleted
    and `git tag` is non-force (fails if the trigger already exists).
    """
    plan: Plan | None = RT(None)
    target_release: str | None = RT(None)   # --publish-only: latest existing rc/final tag
    create_only: bool = RT(False)
    flavor: str = RT()                  # "pre" | "prod"
    release_tag: str | None = RT(T.STICKY)

    def release_tag_get(self) -> str | None:
        if self.target_release:
            return self.target_release
        if self.plan and self.plan.act:
            return self.plan.tag
        return None

    def tag_get(self) -> str | None:
        if not self.release_tag:
            return None
        return VersionHelpers.publish_trigger_tag(self.release_tag, self.flavor)

    def stale_tags_get(self) -> list[str]:
        if self.create_only or not self.tag:
            return []
        return VersionHelpers.existing_publish_trigger_tags(
            GitHelpers.list_tags(self.repo, f"{self.flavor}/*"),
            self.pkg.tag_prefix)

    def tag_commit_get(self) -> str | None:
        if not self.release_tag:
            return None
        return GitHelpers.tag_commit(self.repo, self.release_tag)

    def isolated_tags_to_push_get(self) -> tuple:
        if not self.tag:
            return ()
        refs: list[str] = []
        if not self.create_only:
            refs.extend(f":refs/tags/{t}" for t in self.stale_tags if t != self.tag)
        refs.append(self.tag)
        return (self.repo, refs)

    def summary_prefix_get(self) -> str:
        return "publish trigger"


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

    def tags_to_push_get(self) -> tuple:
        return (self.repo, ["main"])

    def apply(self) -> None:
        GitHelpers.git(self.repo, "checkout", "main")
        if self.forward_pins and PyProjectHelpers.write_forward_pins(self.pkg.pyproject, self.forward_pins) or \
           self.test_pin and PyProjectHelpers.write_test_group(self.pkg.pyproject, self.test_pin):
            GitHelpers.git(self.repo, "commit", "-am", self.description)


class YankTagStep(Step):
    """yank: rename a tag to `<tag>_yanked` (and delete the original), pushing both refs."""
    repo: Path = RT()
    tag: str = RT()
    is_prod: bool = RT(False)
    yanked: str = RT(T.STICKY)
    publish_trigger: str = RT(T.STICKY)

    def yanked_get(self) -> str:
        return f"{self.tag}_yanked"

    def publish_trigger_get(self) -> str:
        flavor = "prod" if self.is_prod else "pre"
        return VersionHelpers.publish_trigger_tag(self.tag, flavor)

    def summary_get(self) -> str:
        return f"rename tag {self.tag} -> {self.yanked}"

    def tags_to_push_get(self) -> tuple:
        return (self.repo, [self.yanked, f":refs/tags/{self.tag}", f":refs/tags/{self.publish_trigger}"])

    def apply(self) -> None:
        GitHelpers.git(self.repo, "tag", self.yanked, self.tag)
        GitHelpers.git(self.repo, "tag", "-d", self.tag)
        GitHelpers.git(self.repo, "tag", "-d", self.publish_trigger, check=False)


class RollbackStep(Step):
    """yank: force the affected `pre`/`prod` pointer back to the previous tag of the same kind."""
    repo: Path = RT()
    branch: str = RT()
    to_tag: str = RT()
    to_commit: str = RT()

    def summary_get(self) -> str:
        return f"roll {self.branch} back to {self.to_tag}"

    def tags_to_push_get(self) -> tuple:
        return (self.repo, [f"+{self.branch}"])

    def apply(self) -> None:
        GitHelpers.git(self.repo, "branch", "-f", self.branch, self.to_commit)


class NoticeStep(Step):
    """A printed-only step (no git mutation, no push) - e.g. the manual PyPI yank instructions."""
    message: str = RT()
    is_mutator = M(False)

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
class XxPromoteCli(TraitableCli):
    """Release promotion for the 10x packages.

    Usage:
    xx-promote pre                                cut the next rc when the package tree changed
    xx-promote pre --no-publish                   cut without creating publish triggers
    xx-promote pre --publish-only                 push publish triggers for the latest rc tags
    xx-promote prod                               promote packages whose latest tag is pre
    xx-promote prod --publish-only                push publish triggers for the latest finals
        xx-promote yank --pkg <name> --version <ver>  yank a tag (rc or final)
        xx-promote status                             list tagged-but-unpublished versions + CI state
        xx-promote resync                             recovery: force local managed refs to origin
    Flags: --dry-run (preview), --push (push to remotes), --publish / --no-publish (create publish
    triggers during pre/prod; default on), --publish-only (triggers only, no cut/promote). --base
    <path> overrides the py10x repo root (default: cwd). Boolean flags also accept the explicit
    `--flag true|false` form.
    """
    dry_run: bool = RT(False)
    push: bool = RT(False)

    base: str = RT(".")
    packages: dict[str, Package] = RT(T.STICKY)
    steps: list[Step] = RT(T.STICKY)
    inputs: list[PkgInput] = RT(T.STICKY)
    completion_command: str = RT(T.STICKY)
    followup_commands: list[str] = RT(T.STICKY)
    idle_message: str | None = RT(T.STICKY)

    s_command: str = None

    def __init_subclass__(cls, _command: str = None, _abstract: bool = False, **kwargs):
        if _abstract:
            super(TraitableCli, cls).__init_subclass__(**kwargs)
        else:
            super().__init_subclass__(_command, **kwargs)
        cls.s_command = _command

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
        result[core_name] = Package(name=core_name, src_dir=base, is_core=True)
        return result

    def inputs_get(self) -> list[PkgInput]:
        """The planners' PkgInputs - each gets the registry and derives the rest via its getters."""
        return [PkgInput(name=name, packages=self.packages) for name in self.packages]

    def followup_commands_get(self) -> list[str]:
        if not self.push and self.completion_command:
            return ['xx-promote resync', f'{self.completion_command} --push']
        return []

    def _push_review_hints(self) -> list[str]:
        """`git` commands to inspect local commits/tags not yet on `origin`."""
        hints: list[str] = []
        seen: set[tuple[Path, str]] = set()
        for s in self.steps:
            for pushed in (s.tags_to_push, s.isolated_tags_to_push):
                repo, refs = pushed if pushed else (None,())
                for ref in refs:
                    if ref.startswith(':refs/tags/') or (repo, ref) in seen:
                        continue
                    seen.add((repo, ref))
                    if ref.startswith('+'):
                        branch = ref[1:]
                        hints += [
                            f'git -C {repo} log --oneline origin/{branch}..{branch}',
                            f'git -C {repo} diff origin/{branch}..{branch}',
                        ]
                    else:
                        label = 'publish trigger' if ref.startswith(('pre/', 'prod/')) else 'tag'
                        hints.append(f'git -C {repo} show {ref}  # {label}')
        return hints

    def _completion_hints(self) -> list[str]:
        """Post-run instructions, or ``None`` when there is nothing to say."""
        if not self.push:
            return ['Local changes applied (not pushed). Review:',
                     *(f'  {h}' for h in self._push_review_hints()),
                     *(f'  {cmd}' for cmd in self.followup_commands)]
        if self.followup_commands:
            return ['Refs pushed. Publish triggers were skipped:',
                    *(f'  {cmd}' for cmd in self.followup_commands)]
        return []

    def _print_completion_hints(self) -> None:
        if self.dry_run:
            return
        if not any(s.is_mutator for s in self.steps):
            if msg := self.idle_message:
                print(f'\n{msg}')
            return
        if lines := self._completion_hints():
            print('\n' + '\n'.join(lines))

    def steps_get(self) -> list[Step]:
        return []

    @staticmethod
    def _atomic_push(repo: Path, refspecs: list[str], label: str = "") -> None:
        refspecs = list(dict.fromkeys(refspecs))
        if not refspecs:
            return
        print(f"  push --atomic {label}{refspecs} -> {repo}")
        GitHelpers.git(repo, "push", "--atomic", "origin", *refspecs)

    @exc_to_rc
    def run_steps(self) -> None:
        # `steps` is T.STICKY, computed once (applying mutates the git state steps_get reads). Apply
        # every local step first; then push bundled refspecs per repo, then each isolated ref alone.
        for s in self.steps:
            print(('  [dry-run] ' if self.dry_run else '  ') + s.summary)
            if not self.dry_run:
                s.verify()
                s.apply()
        if self.dry_run:
            return
        if not self.push:
            self._print_completion_hints()
            return
        by_repo: dict[Path, list[str]] = {}
        for s in self.steps:
            if s.tags_to_push:
                repo, refspecs = s.tags_to_push
                by_repo.setdefault(repo, []).extend(refspecs)
        for repo, refspecs in by_repo.items():
            self._atomic_push(repo, refspecs)
        for s in self.steps:
            if s.isolated_tags_to_push:
                repo, refspecs = s.isolated_tags_to_push
                for refspec in refspecs:
                    self._atomic_push(repo, [refspec], label="isolated ")
        self._print_completion_hints()

    @exc_to_rc
    def post_verify(self) -> None:
        if not self.dry_run:
            repo_globs: dict[Path, list[str]] = {}
            for p in self.packages.values():
                repo_globs.setdefault(p.repo, []).append(f'{p.tag_prefix}*')
                repo_globs[p.repo].extend(VersionHelpers.publish_trigger_globs(p.tag_prefix))
            for repo, globs in repo_globs.items():
                GitHelpers.require_synced(repo, globs)

        if not next(reversed(self.packages.values())).is_core:
            return RuntimeError('The core package must be last.')


    def run(self) -> RC:
        if not self.s_command:
            return RC(False, self.__doc__)
        if not (rc := self.verify()):
            return rc
        if title := (self.__doc__ or "").strip().splitlines():
            print(title[0])                            # just the one-line title, not the whole docstring
        return self.run_steps()


class XxPromote(XxPromoteCli, _abstract=True):
    """Shared `pre` / `prod` promote path (planner batch + optional publish triggers)."""
    publish: bool = RT(True)
    publish_only: bool = RT(False)

    def _create_batch(self):
        raise NotImplementedError()

    def _promote_steps(self) -> list[Step]:
        """The one shared pre/prod routine: a PromoteStep per package (cut or stack, per `plan_cls`)
        plus each plan's `main` epilogue. Flavors differ only in `plan_cls` - same execution path."""
        pkgs = self.packages
        plans = self._create_batch()
        steps: list[Step] = [PromoteStep(pkg=pkg, plan=plans[name]) for name, pkg in pkgs.items()]
        steps += [MainEditStep(pkg=pkgs[name], forward_pins=e.forward_pins, test_pin=e.test_pin,
                               description=e.description)
                  for name, plan in plans.items() for e in plan.epilogue]
        steps += [MainDevMarkerStep(pkg=pkgs[name], plan=plans[name]) for name in pkgs if plans[name].act]
        if self.publish:
            steps += [PublishTriggerStep(pkg=pkgs[name], plan=plans[name], flavor=self.s_command)
                      for name in pkgs if plans[name].act]
        return steps

    def _publish_trigger_steps(self) -> list[Step]:
        """`--publish-only`: create-only triggers for latest releases that lack one."""
        flavor = self.s_command
        missing: list[tuple[str, str]] = []
        for inp in self.inputs:
            release = VersionHelpers.publish_release_tag(inp.parsed_tags, flavor)
            if not release:
                continue
            trigger = VersionHelpers.publish_trigger_tag(release, flavor)
            if not GitHelpers.list_tags(inp.repo, trigger):
                missing.append((inp.name, release))
        return [
            PublishTriggerStep(
                pkg=self.packages[name], flavor=flavor, target_release=release, create_only=True)
            for name, release in missing
        ]

    def steps_get(self) -> list[Step]:
        return self._publish_trigger_steps() if self.publish_only else self._promote_steps()

    def idle_message_get(self) -> str:
        return 'All publish triggers already present; nothing to do.' if self.publish_only else ''

    def completion_command_get(self) -> str:
        parts = [f'xx-promote {self.s_command}']
        if self.publish_only:
            parts.append('--publish-only')
        elif not self.publish:
            parts.append('--no-publish')
        return ' '.join(parts)

    def followup_commands_get(self) -> list[str]:
        if not self.push:
            return super().followup_commands_get()
        if self.publish_only or self.publish:
            return []
        if not any(isinstance(s, PromoteStep) and s.plan.act for s in self.steps):
            return []
        return [f'xx-promote {self.s_command} --publish-only --push']

    def post_verify(self) -> RC:
        rc = super().post_verify()
        if self.publish_only and not self.publish:
            rc.add_error("Cannot specify both --publish-only and --no-publish")
        return rc

class Pre(XxPromote, _command="pre"):
    """xx-promote pre  (cut the next coordinated rc onto the tool-owned `pre` branch)."""
    def _create_batch(self): return PrePlan.create_batch(self.inputs)


class Prod(XxPromote, _command='prod'):
    """xx-promote prod  (stack the final on the latest rc; force-update the `prod` branch)."""
    def _create_batch(self): return ProdPlan.create_batch(self.inputs)

class Yank(XxPromoteCli, _command="yank"):
    """xx-promote yank  (yank the latest tag - rc or final - and roll the pre/prod pointer back)."""
    pkg: str = T(T.NOT_EMPTY)           # distribution name (the --pkg arg)
    version: str = T(T.NOT_EMPTY)

    def completion_command_get(self) -> str:
        return f'xx-promote yank --pkg {self.pkg} --version {self.version}'

    # Shared, sticky-cached derivations used by both post_verify and steps_get.
    package: Package = RT(T.STICKY)     # the resolved Package for `pkg`
    tag: str = RT(T.STICKY)             # the tag being yanked, f"{tag_prefix}{version}"
    parsed: list = RT(T.STICKY)         # the package's parsed tags (yanked excluded)
    is_prod: bool = RT(T.STICKY)        # final (prod) vs rc (pre) yank
    branch_name: str = RT(T.STICKY)     # branch name - pre or prod
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

    def branch_name_get(self) -> str:
        return 'prod' if self.is_prod else 'pre'

    def core_get(self) -> Package:
        return next(p for p in self.packages.values() if p.is_core)

    @exc_to_rc
    def post_verify(self) -> None:
        """Preconditions (run by verify() before run(); exc_to_rc -> RC): known package + tag, synced, latest-only."""
        super().post_verify().throw()
        if self.pkg not in self.packages:
            raise RuntimeError(f'unknown package {self.pkg!r}; choose from {", ".join(self.packages)}')
        if not GitHelpers.list_tags(self.package.repo, self.tag):
            raise RuntimeError(f'tag {self.tag!r} not found in {self.package.repo}')
        if not self.dry_run:
            GitHelpers.require_synced(self.package.repo, [
                f'{self.package.tag_prefix}*', *VersionHelpers.publish_trigger_globs(self.package.tag_prefix)])
        # Stage 1 yanks the latest release only (an older one would orphan everything after it and
        # needs `--cascade`, Stage 2). The tag-found check above guarantees `latest` is not None.
        latest = VersionHelpers.latest_tag(self.parsed)
        if latest is None or Version(self.version) != latest[1]:
            raise RuntimeError(f'{self.tag} is not the latest tag ({latest[0] if latest else "none"}); '
                               f'yanking an older release needs --cascade (Stage 2, not yet available)')

    def steps_get(self) -> list[Step]:
        repo = self.package.repo
        print(f'xx-promote yank {self.pkg} {self.version}  ({self.branch_name})\n')
        steps: list[Step] = [YankTagStep(repo=repo, tag=self.tag, is_prod=self.is_prod)]

        # Roll the affected pointer back to the previous tag of the same kind (rc -> pre, final ->
        # prod), pushed so a --push yank finishes local==remote. Computed at plan time (the previous
        # tag is known); the generic reconcile can't see this move since the rename happens at apply.
        remaining = [(t, v) for t, v in self.parsed if v != Version(self.version)]
        prev_tag = (VersionHelpers.latest_final_tag(remaining) if self.is_prod
                    else VersionHelpers.latest_rc_tag_overall(remaining))
        if prev_tag is not None:
            branch = GitHelpers.release_branch(
                self.branch_name, self.pkg, self.package.is_core)
            steps.append(RollbackStep(repo=repo, branch=branch, to_tag=prev_tag,
                                      to_commit=GitHelpers.tag_commit(repo, prev_tag)))

        # Roll back py10x-core `main` forward pin(s) for the yanked release line.
        if self.package.is_core:
            forward_pins = {
                name: VersionHelpers.main_forward_pin_from_selection(
                    VersionHelpers.parse_pkg_tags(
                        GitHelpers.list_tags(pkg.repo, f"{pkg.tag_prefix}*"), pkg.tag_prefix))
                for name, pkg in self.packages.items() if not pkg.is_core
            }
        else:
            forward_pins = {
                self.pkg: VersionHelpers.main_forward_pin_from_selection(remaining),
            }
        if forward_pins:
            steps.append(MainEditStep(
                pkg=self.core,
                forward_pins=forward_pins,
                description=f"roll back main pin(s) after yanking {self.pkg} v{self.version}"))

        on_pypi = Version(self.version) in PyPIHelpers.published_versions(self.pkg)
        manage_url = f'https://pypi.org/manage/project/{self.pkg}/release/{self.version}/'
        if on_pypi:
            pypi_line = (f'MANUAL: {self.pkg} {self.version} is on PyPI — open the release page and click Yank:\n'
                         f'      {manage_url}')
        else:
            pypi_line = (f'NOTE: {self.pkg} {self.version} is not on PyPI yet — no index action needed.\n'
                         f'      {manage_url}')
        steps.append(NoticeStep(message=pypi_line))
        return steps


class Status(XxPromoteCli, _command="status"):
    """xx-promote status  (pending promotions: tags pushed but the version isn't on PyPI yet)

    For each package it compares local tags (rc + final; `*_yanked` and `*.dev` main markers
    excluded) against PyPI and reports tags pushed since the latest PyPI release that are not on the
    index yet. For each pending tag it resolves the publish workflow run and reports its state and a
    link. Read-only: no git or remote mutation, ignores --dry-run / --push.
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
            for tag, ver in pending:
                flavor = VersionHelpers.publish_trigger_flavor(ver)
                trigger = VersionHelpers.publish_trigger_tag(tag, flavor)
                if slug in gh_errors:
                    state, url = "unknown (gh unavailable)", ""
                else:
                    state, url = GitHubHelpers.publish_workflow_state(
                        runs, trigger,
                        release_on_origin=GitHelpers.tag_on_origin(pkg.repo, tag),
                        trigger_on_origin=GitHelpers.tag_on_origin(pkg.repo, trigger),
                    )
                print(f"      {tag}  workflow ({trigger}): {state}{('  ' + url) if url else ''}")
        if not any_pending:
            print("\nNothing pending since the latest PyPI release.")
        for slug, err in gh_errors.items():
            print(f"\nnote: workflow state for {slug} is unavailable: {err}")
        return RC_TRUE


class Resync(XxPromoteCli, _command="resync"):
    """xx-promote resync  (recovery: discard local work, force managed refs to match origin).

    After a crash, `require_synced` refuses the next promote until local == remote (atomic pushes keep
    the remote consistent, so it is the source of truth). This resyncs each repo - fetch origin, then
    force `main`/`pre`/`prod` branches and the managed tags to their origin counterpart, deleting
    local-only ones - so you can re-run cleanly. Destructive; preview with --dry-run. No-op without an
    `origin`. (CLI command words must be identifiers, so this is `resync`, not `reset-local`.)
    """
    push = M(True)
    followup_commands = M([])

    def post_verify(self) -> RC:
        return RC_TRUE   # recovery runs *because* local != remote - never require_synced here

    def steps_get(self) -> list[Step]:
        repo_branches: dict[Path, set[str]] = {}
        repo_globs: dict[Path, list[str]] = {}
        for name, pkg in self.packages.items():
            repo_branches.setdefault(pkg.repo, {"main"}).update(
                (GitHelpers.release_branch("pre", name, pkg.is_core),
                 GitHelpers.release_branch("prod", name, pkg.is_core)))
            repo_globs.setdefault(pkg.repo, []).append(f"{pkg.tag_prefix}*")
            repo_globs[pkg.repo].extend(VersionHelpers.publish_trigger_globs(pkg.tag_prefix))
        return [ResetRepoStep(repo=repo, branches=sorted(repo_branches[repo]), tag_globs=repo_globs[repo])
                for repo in repo_branches]


def main() -> int:
    rc, inst = XxPromoteCli.from_command_line()
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
