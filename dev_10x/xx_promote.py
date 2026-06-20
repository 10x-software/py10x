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
from typing import Callable

import tomlkit
from packaging.version import Version

from core_10x.exec_control import CONVERT_VALUES_ON
from core_10x.rc import exc_to_rc
from core_10x.trait_definition import RT
from core_10x.traitable import RC, RC_TRUE, T, Traitable
from core_10x.traitable_cli import TraitableCli
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
# Planning
# --------------------------------------------------------------------------------------------
class Step(Traitable):
    """A single side-effecting action, rendered in dry-run and executed otherwise."""
    summary: str
    apply: Callable
    push_refs: tuple[Path, list[str]]

    def push(self):
        if self.push_refs:
            repo, refspecs = self.push_refs
            print(f"  push {refspecs} -> {repo}")
            GitHelpers.git(repo, "push", "origin", *refspecs)


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
    Flags: --dry-run (preview), --push (push to remotes). --base <path> overrides the py10x repo
    root (default: cwd). Boolean flags also accept the explicit `--flag true|false` form.
    """
    dry_run: bool = RT(False)   # converted from the CLI string by CONVERT_VALUES_ON (see below)
    push: bool = RT(False)
    base: str = RT(".")

    packages: dict[str, Package] = RT()
    steps: list[Step] = RT()

    @classmethod
    def instance_from_args(cls, input_args: tuple) -> tuple:
        # traitable_cli stores values verbatim unless conversion is enabled; this turns the
        # `--dry-run` shortcut (stored as the string "true") into a real bool, and would coerce
        # numeric/enum traits too.
        with CONVERT_VALUES_ON():
            return super().instance_from_args(input_args)

    def packages_get(self) -> dict[str, Package]:
        """Build the package registry from `[tool.dev_10x.siblings]` in `base/pyproject.toml`.

        Sibling repo roots are discovered via `git rev-parse --show-toplevel`; tag prefixes follow
        the naming convention `{name}-v` unless overridden by a `tag_prefix` key in the inline table.
        """
        base = Path(self.base).resolve()
        doc = tomlkit.parse((base / "pyproject.toml").read_text(encoding="utf-8"))
        core_name = str(doc["project"]["name"])
        siblings = doc.get("tool", {}).get("dev_10x", {}).get("siblings", {})
        result = {core_name: Package(name=core_name, src_dir=base, tag_prefix="v")}
        result.update(
            (name, Package(name=name, src_dir=(base / spec["path"]).resolve())) for name, spec in siblings.items()
        )
        return result

    @exc_to_rc
    def run_steps(self) -> None:
        for s in self.steps:
            print(('  [dry-run] ' if self.dry_run else '  ') + s.summary)
            if self.dry_run:
                continue
            s.apply()
            if not self.push:
                print('\nLocal changes applied. Review with `git log`/`git status`; re-run with push=true to publish.')
                continue
            s.push()

    def run(self) -> RC:
        rc = self.verify()
        if not rc:
            return rc
        if not self.steps:
            # bare `xx-promote` with no command -> usage
            return RC(False, self.__doc__)
        print(self.__doc__)
        return self.run_steps()


class Pre(XxPromote, _command="pre"):
    """xx-promote pre  (cut release candidates - tagging only when changes detected)"""
    def steps_get(self) -> list[Step]:
        steps: list[Step] = []
        pkgs = self.packages
        if not self.dry_run:
            for repo in {p.repo for p in pkgs.values()}:
                GitHelpers.require_clean(repo)
        for pkg in pkgs.values():
            parsed = VersionHelpers.parse_pkg_tags(GitHelpers.list_tags(pkg.repo, f"{pkg.tag_prefix}*"), pkg.tag_prefix)
            target = VersionHelpers.target_version(parsed)
            head = GitHelpers.git(pkg.repo, "rev-parse", "HEAD")
            pathspecs = GitHelpers.diff_pathspecs(pkg.repo, pkg.src_dir)

            # Skip when those paths are unchanged since the latest pre or prod tag. When that tag is
            # an rc, still offer to push it (local-only `pre` then `pre push=true`).
            if (latest_pair := VersionHelpers.latest_tag(parsed)) is not None:
                ref_tag, ref_ver = latest_pair
                if not GitHelpers.tree_changed_since_tag(pkg.repo, ref_tag, *pathspecs):
                    push_refs = () if VersionHelpers.is_final(ref_ver) else (pkg.repo, [ref_tag])
                    steps.append(Step(
                        summary=f"{pkg.name}: no diff in {', '.join(pathspecs)} since {ref_tag} ({head[:10]}) - skip",
                        apply=lambda: None,
                        push_refs=push_refs,
                    ))
                    continue

            n = VersionHelpers.next_rc(parsed, target)
            tag = f"{pkg.tag_prefix}{target}rc{n}"
            steps.append(Step(
                summary=f"{pkg.name}: tag {tag} at {head[:10]} (HEAD)",
                apply=lambda repo=pkg.repo, tag=tag: GitHelpers.git(repo, "tag", tag),
                push_refs=(pkg.repo, [tag]),
            ))
        return steps


class Prod(XxPromote, _command="prod"):
    """xx-promote prod  (promote when latest tag is pre)"""

    def steps_get(self) -> list[Step]:
        pkgs = self.packages
        if not self.dry_run:
            for repo in {p.repo for p in pkgs.values()}:
                GitHelpers.require_clean(repo)

        core_name = next(n for n in pkgs if pkgs[n].tag_prefix == "v")
        sibling_names = [n for n in pkgs if n != core_name]

        # 1. Resolve each package's rc + target up front (cross-references need all targets).
        targets: dict[str, str] = {}
        rc_commit: dict[str, str] = {}
        for name, pkg in pkgs.items():
            parsed = VersionHelpers.parse_pkg_tags(GitHelpers.list_tags(pkg.repo, f"{pkg.tag_prefix}*"), pkg.tag_prefix)
            target = VersionHelpers.target_version(parsed)
            if (latest_pair := VersionHelpers.latest_tag(parsed)) is None or VersionHelpers.is_final(latest_pair[1]):
                label = latest_pair[0] if latest_pair else "none"
                print(f"  skip {name}: latest tag {label} is not a pre-release")
                continue
            latest_rc = VersionHelpers.latest_rc_tag(parsed, target)
            if latest_rc is None:
                print(f"  skip {name}: no rc tag for target {target}")
                continue
            targets[name] = target
            rc_commit[name] = GitHelpers.tag_commit(pkg.repo, latest_rc)
            print(f"  {name}: promoting rc {latest_rc} ({rc_commit[name][:10]}) -> final v{target}")
        if not targets:
            print("  nothing to promote.")
            return []
        print()

        core_t = targets.get(core_name)
        sib_final = {n: VersionHelpers.final_pin(targets[n]) for n in sibling_names if n in targets}
        sib_dev = {n: VersionHelpers.dev_pin(targets[n], VersionHelpers.next_micro(targets[n])) for n in sibling_names if n in targets}

        steps: list[Step] = []
        for name in targets:
            pkg = pkgs[name]
            t = targets[name]
            branch = f"release/{pkg.tag_prefix}{t}"
            final_tag = f"{pkg.tag_prefix}{t}"

            # 2. Release branch off the rc commit + final-only pins committed there + final tag.
            steps.append(Step(
                summary=f"{name}: branch {branch} off {rc_commit[name][:10]}",
                apply=lambda repo=pkg.repo, branch=branch, commit=rc_commit[name]: GitHelpers.git(repo, "branch", "-f", branch, commit),
            ))

            if name == core_name and sib_final:
                def edit_core(pkg=pkg, branch=branch, t=t):
                    GitHelpers.git(pkg.repo, "checkout", branch)
                    ch = PyProjectHelpers.write_forward_pins(pkg.pyproject, sib_final)
                    GitHelpers.git(pkg.repo, "commit", "-am", f"release v{t}: pin siblings to prod")
                    return ch
                steps.append(Step(
                    summary=f"{name}: on {branch}, set forward pins {sib_final} + commit",
                    apply=edit_core,
                ))
            elif name in sibling_names and core_t:
                def edit_sib(pkg=pkg, branch=branch, t=t):
                    GitHelpers.git(pkg.repo, "checkout", branch)
                    ch = PyProjectHelpers.write_test_group(pkg.pyproject, VersionHelpers.test_group_pin(core_t))
                    GitHelpers.git(pkg.repo, "commit", "-am", f"release v{t}: pin py10x-core test dep")
                    return ch
                steps.append(Step(
                    summary=f"{name}: on {branch}, set test group {core_name}=={core_t} + commit",
                    apply=edit_sib,
                ))

            steps.append(Step(
                summary=f"{name}: tag {final_tag} on {branch}",
                apply=lambda repo=pkg.repo, tag=final_tag, branch=branch: GitHelpers.git(repo, "tag", tag, branch),
                push_refs=(pkg.repo, [branch, final_tag]),
            ))

        # 3. main bump: advance the prerelease-admitting dev-pin floor / reverse group to the just-released versions.
        repos_to_main = {p.repo for n, p in pkgs.items() if n in targets}
        for repo in repos_to_main:
            steps.append(Step(
                summary=f"checkout main in {repo}",
                apply=lambda repo=repo: GitHelpers.git(repo, "checkout", "main"),
            ))

        if sib_dev and core_name in pkgs:
            core = pkgs[core_name]
            steps.append(Step(
                summary=f"main: {core_name} forward dev pins -> {sib_dev} + commit",
                apply=lambda: (PyProjectHelpers.write_forward_pins(core.pyproject, sib_dev),
                               GitHelpers.git(core.repo, "commit", "-am", "bump sibling dev pins after prod promotion")),
                push_refs=(core.repo, ["main"]),
            ))
        if core_t:
            for name in (n for n in sibling_names if n in targets):
                pkg = pkgs[name]
                steps.append(Step(
                    summary=f"main: {name} test group -> {core_name}=={core_t} + commit",
                    apply=lambda pkg=pkg: (
                        PyProjectHelpers.write_test_group(pkg.pyproject, VersionHelpers.test_group_pin(core_t)),
                        GitHelpers.git(pkg.repo, "commit", "-am", "track released py10x-core in test group"),
                    ),
                    push_refs=(pkg.repo, ["main"]),
                ))
        return steps


class Yank(XxPromote, _command="yank"):
    pkg: str = T(T.NOT_EMPTY)
    version: str = T(T.NOT_EMPTY)

    def steps_get(self) -> list[Step]:
        pkgs = self.packages
        pkg_name = self.pkg
        version = self.version
        if pkg_name not in pkgs:
            raise SystemExit(f'unknown package {pkg_name!r}; choose from {", ".join(pkgs)}')
        pkg = pkgs[pkg_name]
        tag = f'{pkg.tag_prefix}{version}'
        if not GitHelpers.list_tags(pkg.repo, tag):
            raise SystemExit(f'tag {tag!r} not found in {pkg.repo}')
        if not self.dry_run:
            GitHelpers.require_clean(pkg.repo)

        is_prod = VersionHelpers.is_final_version_string(version)
        print(f'xx-promote yank {pkg_name} {version}  ({"prod" if is_prod else "pre"})\n')

        core_name = next(n for n in pkgs if pkgs[n].tag_prefix == "v")
        sibling_names = {n for n in pkgs if n != core_name}

        steps: list[Step] = [
            Step(
                summary=f'{pkg_name}: rename tag {tag} -> {(yanked := f"{tag}_yanked")}',
                apply=lambda: (GitHelpers.git(pkg.repo, 'tag', yanked, tag), GitHelpers.git(pkg.repo, 'tag', '-d', tag)),
                push_refs=(pkg.repo, [yanked, f':refs/tags/{tag}']),
            )
        ]

        if is_prod and pkg_name in sibling_names:
            # The yanked final disappears from version selection (its tag no longer parses), so the
            # new floor is whatever final remains; rewrite core's main dev pin to match.
            core = pkgs[core_name]

            def rollback():
                parsed = VersionHelpers.parse_pkg_tags(GitHelpers.list_tags(pkg.repo, f'{pkg.tag_prefix}*'), pkg.tag_prefix)
                lf = VersionHelpers.latest_final(parsed)
                floor = VersionHelpers.base_version(lf) if lf is not None else '0.0.0'
                t = VersionHelpers.next_micro(floor)
                PyProjectHelpers.write_forward_pins(core.pyproject, {pkg_name: VersionHelpers.dev_pin(floor, t)})
                GitHelpers.git(core.repo, 'commit', '-am', f'roll back {pkg_name} dev pin after yanking v{version}')

            steps.append(Step(
                summary=f'main: roll back {core_name} {pkg_name} dev pin to latest non-yanked release',
                apply=rollback,
                push_refs=(core.repo, ['main']),
            ))

        # The index yank itself is manual: PyPI has no public yank API (it is a session-authenticated
        # web action), so there is no CI workflow for it - we just print what to do.
        manage_url = f'https://pypi.org/manage/project/{pkg_name}/release/{version}/'
        steps.append(Step(
            summary=(f'MANUAL: PyPI has no yank API - yank {pkg_name} {version} on the index yourself:\n'
                     f'      {manage_url}  (Options -> Yank)'),
            apply=lambda: None,
        ))
        return steps


class Status(XxPromote, _command="status"):
    """xx-promote status  (pending promotions: tags pushed but the version isn't on PyPI yet)

    For each package it compares local tags (rc + final, yanked tags excluded) against PyPI and
    reports tags pushed since the latest PyPI release that are not on the index yet. For each
    pending tag it resolves the publish workflow run and reports its state and a link. Read-only:
    no git or remote mutation, ignores --dry-run / --push.
    """

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
