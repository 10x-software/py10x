from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version, InvalidVersion
import tomlkit


class VersionHelpers:
    # A no-op lower bound (every version satisfies it) whose only job is to name a pre-release in an
    # *inclusive* operator, which flips on uv's per-package pre-release admission
    # (`SpecifierSet.prereleases`) without `--prerelease=allow`.
    PRERELEASE_ENABLE = '>=0.0.0.dev0'

    # --------------------------------------------------------------------------------------------
    # Pure helpers (no I/O) - exercised directly by the unit tests.
    # --------------------------------------------------------------------------------------------
    YANKED_SUFFIX = "_yanked"
    PUBLISH_PRE_PREFIX = "pre/"
    PUBLISH_PROD_PREFIX = "prod/"

    @classmethod
    def publish_trigger_prefix(cls, flavor: str) -> str:
        if flavor not in ("pre", "prod"):
            raise ValueError(f"unknown publish flavor {flavor!r}")
        return cls.PUBLISH_PRE_PREFIX if flavor == "pre" else cls.PUBLISH_PROD_PREFIX

    @classmethod
    def publish_trigger_tag(cls, release_tag: str, flavor: str) -> str:
        """CI-only tag on the release commit — workflows listen here, not on the release tag."""
        return f"{cls.publish_trigger_prefix(flavor)}{release_tag}"

    @classmethod
    def publish_trigger_globs(cls, tag_prefix: str) -> tuple[str, str]:
        return (f"{cls.PUBLISH_PRE_PREFIX}{tag_prefix}*", f"{cls.PUBLISH_PROD_PREFIX}{tag_prefix}*")

    @classmethod
    def existing_publish_trigger_tags(cls, raw_tags: list[str], release_prefix: str) -> list[str]:
        """Prior publish triggers for one package (one canonical trigger; pre or prod)."""
        return [
            t for t in raw_tags
            if cls.is_publish_trigger_tag(t) and t.split("/", 1)[1].startswith(release_prefix)
        ]

    @classmethod
    def publish_trigger_flavor(cls, version: Version) -> str:
        return "prod" if cls.is_final(version) else "pre"

    @classmethod
    def is_publish_trigger_tag(cls, tag: str) -> bool:
        return tag.startswith((cls.PUBLISH_PRE_PREFIX, cls.PUBLISH_PROD_PREFIX))

    @classmethod
    def is_main_dev_marker(cls, v: Version) -> bool:
        """A `.dev` tag on `main` for setuptools-scm — not a publishable release.

        Two shapes: `{T}rc{N}.dev` (next-rc-line marker set by `pre`) and `{T}rc0.dev` (post-final
        marker set by `prod`, where `T` is `next_micro` of the released final).
        """
        if not v.is_devrelease:
            return False
        if v.pre is not None and v.pre[0] == "rc":
            return True
        return not v.is_postrelease

    @classmethod
    def main_dev_marker_tag(cls, release_tag: str, prefix: str) -> str:
        """Companion marker on `main` when cutting rcN: `{prefix}{T}rc(N+1).dev`.

        Placed on `main` HEAD at the fork so setuptools-scm on `main` reads as the *next* rc line
        while the publishable rcN tag lives on `pre`.
        """
        if not release_tag.startswith(prefix):
            raise ValueError(f"{release_tag!r} does not start with {prefix!r}")
        ver = Version(release_tag[len(prefix):])
        if ver.pre is None or ver.pre[0] != "rc":
            raise ValueError(f"{release_tag!r} is not an rc release tag")
        target = cls.base_version(ver)
        return f"{prefix}{target}rc{ver.pre[1] + 1}.dev"

    @classmethod
    def main_post_final_dev_marker_tag(cls, final_tag: str, prefix: str) -> str:
        """Companion marker on `main` after `prod`: `{prefix}{next_micro(T)}rc0.dev`.

        Keeps setuptools-scm on `main` strictly above the just-published final `{T}` while anchoring
        the *next* micro's rc line (a stale `{T}rc(N+1).dev` rc-line marker would rank below `{T}`).
        """
        if not final_tag.startswith(prefix):
            raise ValueError(f"{final_tag!r} does not start with {prefix!r}")
        ver = Version(final_tag[len(prefix):])
        if not cls.is_final(ver):
            raise ValueError(f"{final_tag!r} is not a final release tag")
        return f"{prefix}{cls.next_micro(cls.base_version(ver))}rc0.dev"

    @classmethod
    def existing_main_dev_marker_tags(cls, raw_tags: list[str], prefix: str) -> list[str]:
        """All `{prefix}*.dev` main markers currently present (rc-line or post-final)."""
        return [
            t for t, v in cls.parse_pkg_tags(raw_tags, prefix, include_dev_markers=True)
            if cls.is_main_dev_marker(v)
        ]

    @classmethod
    def parse_pkg_tags(
        cls, raw_tags: list[str], prefix: str, include_yanked: bool = False,
        include_dev_markers: bool = False,
    ) -> list[tuple[str, Version]]:
        """Strip `prefix` from each tag and parse the remainder as a PEP 440 version.

        Tags that don't start with `prefix` or don't parse are dropped. For *selection* (the default),
        yanked `..._yanked` tags and `{T}*.dev` main scm markers are dropped; yanked tags are included
        — with their `_yanked` stripped before parsing — when `include_yanked` is set, for
        *generation*: a yanked version number is consumed (PyPI forbids re-upload), so the next-version
        floor must count it even though selection won't. Main markers are included only when
        `include_dev_markers` is set.
        """
        out: list[tuple[str, Version]] = []
        for tag in raw_tags:
            if not tag.startswith(prefix):
                continue
            rest = tag[len(prefix):]
            if rest.endswith(cls.YANKED_SUFFIX):
                if not include_yanked:
                    continue
                rest = rest[: -len(cls.YANKED_SUFFIX)]
            try:
                ver = Version(rest)
            except InvalidVersion:
                continue
            if not include_dev_markers and cls.is_main_dev_marker(ver):
                continue
            out.append((tag, ver))
        return out

    @staticmethod
    def is_final(v: Version) -> bool:
        return not v.is_prerelease and not v.is_devrelease

    @classmethod
    def is_final_version_string(cls, version_string: str) -> bool:
        return cls.is_final(Version(version_string))

    @classmethod
    def latest_final(cls, parsed: list[tuple[str, Version]]) -> Version | None:
        """Highest released (non pre/dev) version, by PEP 440 ordering.

        `max()` over `Version` is used deliberately: `git --sort=-v:refname` / `sort -V` misorder
        pre-releases (they rank `0.2.3` below `0.2.3rc1`).
        """
        finals = [v for _, v in parsed if cls.is_final(v)]
        return max(finals) if finals else None

    @staticmethod
    def latest_matching_tag(parsed: list[tuple[str, Version]], spec: str) -> str | None:
        """The highest tag whose version satisfies `spec` (a PEP 440 specifier string), or None.

        `SpecifierSet.filter` honours the set's own pre-release flag, so a prerelease-admitting dev pin selects
        the latest rc while a final-only pin selects the latest final - i.e. exactly what a consumer
        of the about-to-be-published pin would resolve to.
        """
        by_ver = {v: t for t, v in parsed}
        eligible = list(SpecifierSet(spec).filter(by_ver))
        return by_ver[max(eligible)] if eligible else None

    @staticmethod
    def base_version(v: Version | str) -> str:
        """The `X.Y.Z` release of a version, zero-padded to three components."""
        v = Version(str(v))
        rel = list(v.release) + [0, 0, 0]
        return f"{rel[0]}.{rel[1]}.{rel[2]}"

    @classmethod
    def next_micro(cls,base: str) -> str:
        """`0.2.0` -> `0.2.1` (the setuptools-scm guess-next-dev bump)."""
        major, minor, micro = (int(p) for p in cls.base_version(base).split("."))
        return f"{major}.{minor}.{micro + 1}"

    @classmethod
    def target_version(cls, parsed: list[tuple[str, Version]]) -> str:
        """The in-development target `T` = next micro after the latest final tag (`0.2.1` if none)."""
        lf = cls.latest_final(parsed)
        return cls.next_micro(cls.base_version(lf)) if lf is not None else "0.0.1"

    @classmethod
    def next_rc(cls, parsed: list[tuple[str, Version]], target: str) -> int:
        """Next rc number for `target`: max existing rc for that base + 1, else 1."""
        rcs = [
            v.pre[1]
            for _, v in parsed
            if cls.base_version(v) == target and v.pre is not None and v.pre[0] == "rc"
        ]
        return (max(rcs) + 1) if rcs else 1

    @classmethod
    def latest_rc_tag(cls, parsed: list[tuple[str, Version]], target: str) -> str | None:
        """The highest-numbered rc tag for `target`, or None - used to skip minting a duplicate."""
        rcs = [(t, v) for t, v in parsed
               if cls.base_version(v) == target and v.pre is not None and v.pre[0] == "rc"]
        return max(rcs, key=lambda tv: tv[1])[0] if rcs else None

    @classmethod
    def latest_tag(cls, parsed: list[tuple[str, Version]]) -> tuple[str, Version] | None:
        """Highest-version tag (rc or final), or None when the package has never been tagged."""
        return max(parsed, key=lambda tv: tv[1]) if parsed else None

    @staticmethod
    def latest_rc_tag_overall(parsed: list[tuple[str, Version]]) -> str | None:
        """Highest-version rc tag across all targets, or None - the commit `pre` derives to."""
        rcs = [(t, v) for t, v in parsed if v.pre is not None and v.pre[0] == "rc"]
        return max(rcs, key=lambda tv: tv[1])[0] if rcs else None

    @classmethod
    def latest_final_tag(cls, parsed: list[tuple[str, Version]]) -> str | None:
        """Highest-version final tag, or None - the commit `prod` derives to."""
        finals = [(t, v) for t, v in parsed if cls.is_final(v)]
        return max(finals, key=lambda tv: tv[1])[0] if finals else None

    @classmethod
    def publish_release_tag(cls, parsed: list[tuple[str, Version]], flavor: str) -> str | None:
        """Latest existing release tag to attach a publish trigger to (`pre` -> rc, `prod` -> final)."""
        if flavor == "pre":
            return cls.latest_rc_tag_overall(parsed)
        if flavor == "prod":
            return cls.latest_final_tag(parsed)
        raise ValueError(f"unknown publish flavor {flavor!r}")

    @classmethod
    def pending_promotions(
        cls,
        parsed: list[tuple[str, Version]],
        published: set[Version],
    ) -> list[tuple[str, Version]]:
        """Tags pushed since the latest PyPI release that are not on PyPI yet, oldest first.

        The floor is `max(published)` — in this project's CI, publish is atomic (the workflow uploads
        to PyPI), so a version on the index is a successful publish. Only tags strictly newer than
        that floor and still absent from PyPI are reported; abandoned pre-PyPI history and superseded
        rc attempts before the last publish stay hidden. When nothing is published yet, just the
        single latest tag is returned (the in-flight first release).
        """
        if not parsed:
            return []
        if not published:
            latest = cls.latest_tag(parsed)
            return [latest] if latest else []
        floor = max(published)
        return sorted(
            [(t, v) for t, v in parsed if v > floor and v not in published],
            key=lambda tv: tv[1],
        )


    @classmethod
    def dev_pin(cls,floor: str, target: str) -> str:
        """Prerelease-admitting dev pin: admits sibling dev/alpha/beta/rc of `target`, excludes its final and beyond.

        `<=target,!=target` includes every pre-release of `target` (unlike `<target`, which the PEP 440
        rules strip pre-releases from) while dropping the final; `PRERELEASE_ENABLE` makes uv consider
        those pre-releases without `--prerelease=allow`.
        """
        return f">={floor},<={target},!={target},{cls.PRERELEASE_ENABLE}"

    @classmethod
    def final_pin(cls,target: str) -> str:
        """Final-only pin for a release branch: admits `target` + its post releases, no pre/dev.

        Legacy `main`-floor / pre-rc-coordination form. The published-wheel forward pin on
        `pre`/`prod` is now `exact_pin` (exact `==`); see `dev_10x/docs/rc-branch-promotion.md`.
        """
        return f">={target},<{cls.next_micro(target)}"

    @staticmethod
    def exact_pin(version: str) -> str:
        """Exact coordinated forward pin for a published wheel (rc or final): `==X.YrcN` / `==X.Y`.

        The external coordination guarantee (core -> siblings on `pre`/`prod`): `==<pre>` auto-enables
        prereleases on its own (no token needed) and `==<final>` admits only that final - not its rc,
        not its `.postN`. Guarded in `test_xx_utils.py` (coordination pin forms).
        """
        return f"=={version}"

    @staticmethod
    def test_group_pin(core_version: str) -> str:
        """Reverse py10x-core test dependency: `>=` the coordinated core version (dev-only, unpublished).

        `>=` not `==`: the prerelease token falls out for free - `>=Trc` admits core prereleases (an
        rc sibling tests the prerelease line), `>=T` admits only finals (a final tests the released
        line). Uncapped but self-correcting via the forward `==` (rc-branch-promotion.md, Pin matrix).
        """
        return f"py10x-core>={core_version}"


class GitHelpers:
    # --------------------------------------------------------------------------------------------
    # git I/O (thin wrappers)
    # --------------------------------------------------------------------------------------------
    @staticmethod
    def git(repo: Path, *args: str, check: bool = True) -> str:
        res = subprocess.run(
            ["git", *args], cwd=repo, text=True, capture_output=True, check=False
        )
        if check and res.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} (in {repo}) failed:\n{res.stderr.strip()}")
        return res.stdout.strip()

    @classmethod
    def list_tags(cls, repo: Path, pattern: str) -> list[str]:
        out = cls.git(repo, "tag", "--list", pattern)
        return [t for t in out.splitlines() if t]

    @classmethod
    def require_clean(cls,repo: Path) -> None:
        if cls.git(repo, "status", "--porcelain"):
            raise RuntimeError(f"working tree not clean: {repo} - commit or stash first")

    @classmethod
    def has_origin(cls, repo: Path) -> bool:
        return "origin" in cls.git(repo, "remote").split()

    @classmethod
    def ls_remote_ref(cls, repo: Path, ref: str) -> str | None:
        """The commit `origin` has for `ref` (e.g. 'refs/heads/main'), live; None when absent."""
        out = cls.git(repo, "ls-remote", "origin", ref)
        return out.split("\t", 1)[0] if out else None

    @classmethod
    def _tags_matching_glob(cls, tags: set[str], pattern: str) -> set[str]:
        """`git tag -l` / `ls-remote` pattern matching differs; compare by prefix instead."""
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return {t for t in tags if t.startswith(prefix)}
        return tags & {pattern}

    @classmethod
    def ls_remote_tags(cls, repo: Path, pattern: str) -> set[str]:
        """Tag names on `origin` matching `pattern` (peeled `^{}` refs collapsed)."""
        out = cls.git(repo, "ls-remote", "--tags", "origin", pattern)
        tags: set[str] = set()
        for line in out.splitlines():
            if "\t" in line:
                tags.add(line.split("\t", 1)[1].removeprefix("refs/tags/").removesuffix("^{}"))
        return cls._tags_matching_glob(tags, pattern)

    @classmethod
    def require_synced(cls, repo: Path, tag_globs: list[str]) -> None:
        """Precondition: working tree clean AND local == origin (fetch-first) for `main` and the
        managed tag globs. Skips the remote half when there is no `origin` (pure-local dev).

        Enforces the "start local==remote (incl. tags)" invariant so a subsequent `--push` finishes
        with local==remote; refuses on a stale/un-pushed `main` or divergent managed tags.
        """
        cls.require_clean(repo)
        if not cls.has_origin(repo):
            return
        cls.git(repo, "fetch", "--quiet", "--prune", "origin")
        remote_main = cls.ls_remote_ref(repo, "refs/heads/main")
        if remote_main is not None and cls.git(repo, "rev-parse", "main") != remote_main:
            raise RuntimeError(f"{repo}: local main != origin/main - push/pull main before promoting")
        for glob in tag_globs:
            local = cls._tags_matching_glob(set(cls.list_tags(repo, glob)), glob)
            remote = cls.ls_remote_tags(repo, glob)
            if local != remote:
                raise RuntimeError(
                    f"{repo}: local tags != origin for {glob} - sync first "
                    f"(only-local={sorted(local - remote)}, only-remote={sorted(remote - local)})")

    @classmethod
    def tag_commit(cls, repo: Path, tag: str) -> str:
        return cls.git(repo, "rev-list", "-n", "1", tag)

    @staticmethod
    def repo_relative_subtree(repo: Path, path: Path) -> str:
        """Repo-relative path for `path` (`.` when `path` is the repo root)."""
        rel = path.resolve().relative_to(repo.resolve())
        return rel.as_posix() if rel.parts else "."

    @staticmethod
    def diff_pathspecs(*sibling_subdirs: str) -> tuple[str, ...]:
        """`git diff` pathspecs for a package's release footprint: the **whole repo minus the other
        packages' subtrees**.

        Rule: a change inside a package's own dir affects that package only; anything *outside* every
        package dir (shared CI, root build config, …) affects all of them. So a package's footprint is
        `.` with each *sibling* subtree excluded - its own files and all shared files count, a
        sibling's subtree does not. A package alone in its repo -> the whole repo (`.`).
        """
        return (".", *(f":(exclude){s}" for s in sibling_subdirs))

    @classmethod
    def tree_changed_since_tag(cls, repo: Path, tag: str, *pathspecs: str, rev: str = "HEAD") -> bool:
        """True when any of `pathspecs` (repo-relative, `.` = whole repo) differs `tag`..`rev`.

        `rev` is the cut base (`main` HEAD for `pre --from=main`); defaults to `HEAD`.
        """
        res = subprocess.run(
            ["git", "diff", "--quiet", tag, rev, "--", *pathspecs],
            cwd=repo, capture_output=True, text=True, check=False,
        )
        if res.returncode == 0:
            return False
        if res.returncode == 1:
            return True
        raise RuntimeError(
            f"git diff --quiet {tag} {rev} -- {' '.join(pathspecs)} (in {repo}) failed:\n{res.stderr.strip()}"
        )

    @classmethod
    def is_ancestor(cls, repo: Path, ancestor: str, descendant: str) -> bool:
        """True iff `ancestor` is an ancestor of `descendant` (`git merge-base --is-ancestor`).

        The `--from=main` reachability gate: `is_ancestor(repo, "main", "HEAD")` must hold so a cut
        is never taken from a stale `main`.
        """
        res = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=repo, capture_output=True, text=True, check=False,
        )
        if res.returncode in (0, 1):
            return res.returncode == 0
        raise RuntimeError(
            f"git merge-base --is-ancestor {ancestor} {descendant} (in {repo}) failed:\n{res.stderr.strip()}"
        )

    @classmethod
    def file_at_ref(cls, repo: Path, ref: str, rel_path: str) -> str | None:
        """Contents of `rel_path` at `ref` (`git show ref:path`), or None when absent at that ref."""
        res = subprocess.run(
            ["git", "show", f"{ref}:{rel_path}"], cwd=repo, capture_output=True, text=True, check=False,
        )
        return res.stdout if res.returncode == 0 else None

    @classmethod
    def git_root(cls, path: Path) -> Path:
        return Path(cls.git(path, "rev-parse", "--show-toplevel"))

    @staticmethod
    def release_branch(flavor: str, name: str, is_core: bool) -> str:
        """Tool-owned release-line branch name for a package (`flavor` in {"pre", "prod"}).

        core (one package per repo) uses the bare `pre`/`prod`; siblings sharing a repo (cxx10x's
        kernel + infra) are namespaced per package, e.g. `pre/py10x-kernel`. See
        `dev_10x/docs/rc-branch-promotion.md` (Branches).
        """
        return flavor if is_core else f"{flavor}/{name}"


class PyProjectHelpers:
    # --------------------------------------------------------------------------------------------
    # pyproject rewrites (tomlkit, format-preserving)
    # --------------------------------------------------------------------------------------------
    def _load(path: Path):

        return tomlkit.parse(path.read_text(encoding="utf-8"))


    def _dump(path: Path, doc) -> None:

        path.write_text(tomlkit.dumps(doc), encoding="utf-8", newline="\n")


    @classmethod
    def dependency_spec(cls, path: Path, name: str) -> str:
        """The version specifier currently pinned for dependency `name` in [project.dependencies]."""
        doc = cls._load(path)
        for entry in doc["project"]["dependencies"]:
            req = Requirement(str(entry))
            if req.name == name:
                return str(req.specifier)
        raise KeyError(f"{name} not in {path} [project.dependencies]")

    @staticmethod
    def exact_pins_from_text(text: str, names: set[str]) -> dict[str, str]:
        """{name: pinned version} for each `name` carrying an exact `==` in a pyproject's deps `text`.

        Reads the forward `==` pins already published on a `pre`/`prod` tag (via `git show`), so the
        planner can decide whether core's current pin lags a sibling's latest tag. Names without an
        `==` specifier (e.g. a `main` dev pin) are omitted.
        """
        doc = tomlkit.parse(text)
        out: dict[str, str] = {}
        for entry in doc.get("project", {}).get("dependencies", []):
            req = Requirement(str(entry))
            if req.name in names:
                exact = [s.version for s in req.specifier if s.operator == "=="]
                if exact:
                    out[req.name] = exact[0]
        return out

    def forward_pin_edits(deps: list[str], pins: dict[str, str]) -> list[str]:
        """Return a new dependency list with `pins` ({name: specifier}) applied, format `name (spec)`."""
        out: list[str] = []
        for entry in deps:
            try:
                name = Requirement(entry).name
            except Exception:
                out.append(entry)
                continue
            out.append(f"{name} ({pins[name]})" if name in pins else entry)
        return out

    @classmethod
    def write_forward_pins(cls,path: Path, pins: dict[str, str]) -> dict[str, str]:
        """Apply forward sibling pins to a [project.dependencies] array. Returns {name: old->new}."""
        doc = cls._load(path)
        deps = doc["project"]["dependencies"]
        before = list(deps)
        after = cls.forward_pin_edits(before, pins)
        changes = {
            Requirement(o).name: f"{o!r} -> {n!r}" for o, n in zip(before, after) if o != n
        }
        for i, entry in enumerate(after):
            deps[i] = entry
        cls._dump(path, doc)
        return changes

    @classmethod
    def write_test_group(cls, path: Path, core_pin: str) -> str:
        """Set/refresh `[dependency-groups] test = [<core_pin>]`. Returns a description of the change."""

        doc = cls._load(path)
        groups = doc.get("dependency-groups")
        if groups is None:
            groups = tomlkit.table()
            doc["dependency-groups"] = groups
        old = list(groups.get("test", []))
        arr = tomlkit.array()
        arr.append(core_pin)
        groups["test"] = arr
        cls._dump(path, doc)
        return f"{old} -> [{core_pin!r}]"


class InstalledSourceHelpers:
    """Query install source metadata for packages in a project `.venv` via `uv pip show`."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    @staticmethod
    def parse_uv_pip_show(stdout: str) -> dict[str, str]:
        """Key/value fields from `uv pip show` stdout (one package block)."""
        info: dict[str, str] = {}
        for line in stdout.splitlines():
            if ': ' in line:
                key, value = line.split(': ', 1)
                info[key.strip()] = value.strip()
        return info

    @staticmethod
    def dist_info_direct_url(show: dict[str, str]) -> str:
        """PEP 610 `direct_url.json` body from `{Location}/{Name}-{Version}.dist-info`, or ''."""
        location, name, version = show.get('Location'), show.get('Name'), show.get('Version')
        if not location or not name or not version:
            return ''
        dist_info = Path(location) / f'{name.replace("-", "_")}-{version}.dist-info'
        direct_url = dist_info / 'direct_url.json'
        return direct_url.read_text(encoding='utf-8') if direct_url.is_file() else ''

    @staticmethod
    def classify_install(
        editable_path: Path | None, direct_url_raw: str,
    ) -> tuple[str, Path | None]:
        """Map `uv pip show` + PEP 610 metadata to (kind, path)."""
        if editable_path is not None:
            return 'local', editable_path
        if not direct_url_raw:
            return 'index', None
        return 'other', None

    def venv_python(self) -> Path | None:
        ex = Path(sys.executable)
        py = self.project_root / '.venv' / ('Scripts' if ex.suffix else 'bin') / ex.name
        if not py.is_file():
            raise RuntimeError(f"Cannot find python in .venv: {py}")
        return py

    def pip_show(self, name: str) -> dict[str, str] | None:
        """`uv pip show` for `name` in the project `.venv`; None when not installed."""
        py = self.venv_python()
        if py is None:
            return None
        proc = subprocess.run(
            ['uv', 'pip', 'show', '--python', str(py), name],
            cwd=self.project_root, capture_output=True, text=True,
        )
        if proc.returncode != 0 or 'Package(s) not found' in proc.stdout + proc.stderr:
            return None
        return self.parse_uv_pip_show(proc.stdout)

    def installed_source(self, name: str) -> tuple[str | None, Path | None]:
        """(kind, path) of the install in the project `.venv`.

        None=not installed, 'index', 'local'(editable), 'other'(git/direct URL wheel).
        """
        info = self.pip_show(name)
        if info is None:
            return None, None
        editable = info.get('Editable project location')
        editable_path = Path(editable) if editable else None
        return self.classify_install(editable_path, self.dist_info_direct_url(info))

    def installed_version(self, name: str) -> str:
        """Installed version of `name` in the project `.venv` (from `uv pip show`)."""
        info = self.pip_show(name)
        if info is None or 'Version' not in info:
            raise RuntimeError(f'{name} is not installed in {self.project_root / ".venv"}')
        return info['Version']


class PyPIHelpers:
    """Query which versions of a distribution are published on PyPI (the JSON simple API)."""

    @staticmethod
    def parse_released_versions(json_text: str) -> set[Version]:
        """Parsed (PEP 440) versions from a PyPI `/pypi/{name}/json` body's `releases` map.

        Unparseable release keys are dropped so a malformed upload never breaks the comparison.
        """
        import json
        data = json.loads(json_text)
        out: set[Version] = set()
        for raw in data.get('releases', {}):
            try:
                out.add(Version(raw))
            except InvalidVersion:
                continue
        return out

    @classmethod
    def published_versions(cls, name: str, timeout: float = 10.0) -> set[Version]:
        """Every version of `name` published on PyPI; empty set when the project has none yet.

        A 404 means the project itself is not on the index (nothing published), which is a normal
        first-release state - not an error.
        """
        from urllib import request, error
        url = f'https://pypi.org/pypi/{name}/json'
        try:
            with request.urlopen(url, timeout=timeout) as resp:
                return cls.parse_released_versions(resp.read().decode('utf-8'))
        except error.HTTPError as e:
            if e.code == 404:
                return set()
            raise


class GhUnavailableError(RuntimeError):
    """`gh` (GitHub CLI) is missing or its API call failed - workflow state can't be resolved."""


class GitHubHelpers:
    """Resolve the GitHub Actions run that a pushed tag triggered, via the `gh` CLI.

    `gh` is used (rather than raw HTTP) so the caller's existing auth covers private repos; its
    absence degrades to `GhUnavailable` rather than failing the whole status report.
    """

    @staticmethod
    def parse_remote_slug(url: str) -> str:
        """`owner/repo` from a git remote URL (scp-like `git@host:o/r.git`, https, or ssh://)."""
        url = url.strip().removesuffix('.git')
        if url.startswith('git@') or (':' in url and '://' not in url):
            # scp-like syntax: git@github.com:owner/repo
            url = url.split(':', 1)[1]
        else:
            # https://github.com/owner/repo or ssh://git@github.com/owner/repo
            url = url.split('://', 1)[-1]
            url = url.split('/', 1)[1] if '/' in url else url
        return '/'.join(url.strip('/').split('/')[-2:])

    @classmethod
    def remote_slug(cls, repo: Path) -> str:
        return cls.parse_remote_slug(GitHelpers.git(repo, 'remote', 'get-url', 'origin'))

    @staticmethod
    def select_run_for_tag(runs: list[dict], tag: str) -> dict | None:
        """The most recent push-triggered run whose ref is `tag` (tags surface as `head_branch`)."""
        matching = [r for r in runs if r.get('head_branch') == tag]
        return max(matching, key=lambda r: r.get('created_at', '')) if matching else None

    @staticmethod
    def run_state(run: dict | None) -> str:
        """Human-readable state: a completed run's conclusion, else its in-flight status."""
        if run is None:
            return 'no workflow run found'
        if run.get('status') == 'completed':
            return run.get('conclusion') or 'completed'
        return run.get('status') or 'unknown'

    @classmethod
    def push_runs(cls, slug: str) -> list[dict]:
        """The 100 most recent push-event workflow runs for `slug` (newest first).

        Raises `GhUnavailableError` when `gh` is not installed or the API call fails.
        """
        import json
        try:
            proc = subprocess.run(
                ['gh', 'api', f'repos/{slug}/actions/runs?event=push&per_page=100',
                 '--jq', '.workflow_runs'],
                capture_output=True, text=True, check=False,
            )
        except FileNotFoundError as e:
            raise GhUnavailableError('gh (GitHub CLI) is not installed') from e
        if proc.returncode != 0:
            raise GhUnavailableError(proc.stderr.strip() or f'gh api failed for {slug}')
        return json.loads(proc.stdout or '[]')
