from __future__ import annotations

import subprocess
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
    @staticmethod
    def parse_pkg_tags(raw_tags: list[str], prefix: str) -> list[tuple[str, Version]]:
        """Strip `prefix` from each tag and parse the remainder as a PEP 440 version.

        Tags that don't start with `prefix` or don't parse (e.g. yanked `..._yanked` tags) are
        dropped, so they never influence version selection.
        """
        out: list[tuple[str, Version]] = []
        for tag in raw_tags:
            if not tag.startswith(prefix):
                continue
            rest = tag[len(prefix):]
            try:
                out.append((tag, Version(rest)))
            except InvalidVersion:
                continue
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

        `SpecifierSet.filter` honours the set's own pre-release flag, so a Form A dev pin selects
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
    def dev_pin(cls,floor: str, target: str) -> str:
        """Form A: admits sibling dev/alpha/beta/rc of `target`, excludes its final and beyond.

        `<=target,!=target` includes every pre-release of `target` (unlike `<target`, which the PEP 440
        rules strip pre-releases from) while dropping the final; `PRERELEASE_ENABLE` makes uv consider
        those pre-releases without `--prerelease=allow`.
        """
        return f">={floor},<={target},!={target},{cls.PRERELEASE_ENABLE}"

    @classmethod
    def final_pin(cls,target: str) -> str:
        """Final-only pin for a release branch: admits `target` + its post releases, no pre/dev."""
        return f">={target},<{cls.next_micro(target)}"

    @staticmethod
    def test_group_pin(core_version: str) -> str:
        """Reverse py10x-core test dependency, pinned exactly to the released core version."""
        return f"py10x-core=={core_version}"


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
    def tag_commit(cls, repo: Path, tag: str) -> str:
        return cls.git(repo, "rev-list", "-n", "1", tag)

    @classmethod
    def git_root(cls, path: Path) -> Path:
        return Path(cls.git(path, "rev-parse", "--show-toplevel"))


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
        deps.clear()
        for entry in after:
            deps.append(entry)
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
        py = self.project_root / '.venv' / 'bin' / 'python'
        return py if py.is_file() else None

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
