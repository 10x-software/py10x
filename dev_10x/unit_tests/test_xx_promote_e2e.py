"""End-to-end execution tests for `xx-promote` against real git repos under `tmp_path`.

A one-repo / 3-package fixture mirrors production: py10x-core at the root, py10x-kernel and
py10x-infra in-tree under `cxx10x/` with the production `footprint` config and tag prefixes. The
plan-level combinatorics live in test_xx_plan.py; here we assert *real git state* after execution -
branch HEADs, tags, commit parentage, and the pyproject pins recorded at the tag.

See `dev_10x/README.md` (xx-promote).
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest
import tomlkit
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet

from dev_10x import xx_promote as xp
from dev_10x.xx_helpers import GitHelpers, VersionHelpers

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.skipif(shutil.which('git') is None, reason='git not available')

DEV_PIN = '>=0.2.0,<=0.2.1,!=0.2.1,>=0.0.0.dev0'  # a prerelease-admitting main dev pin


def _init(repo, branch='main'):
    repo.mkdir(parents=True, exist_ok=True)
    GitHelpers.git(repo, 'init', '-q', '-b', branch)
    GitHelpers.git(repo, 'config', 'user.email', 'test@example.com')
    GitHelpers.git(repo, 'config', 'user.name', 'Test')


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


KERNEL_DIR = 'cxx10x/core_10x'
INFRA_DIR = 'cxx10x/infra_10x'
SIBLINGS = (('py10x-kernel', KERNEL_DIR), ('py10x-infra', INFRA_DIR))


def _siblings_toml() -> str:
    def entry(name, path, other):
        return f'{name} = {{ path = "{path}", footprint = ["cxx10x", ":(exclude){other}"] }}\n'

    return '[tool.dev_10x.siblings]\n' + entry('py10x-kernel', KERNEL_DIR, INFRA_DIR) + entry('py10x-infra', INFRA_DIR, KERNEL_DIR)


def _commit_all(repo, msg):
    GitHelpers.git(repo, 'add', '.')
    GitHelpers.git(repo, 'commit', '-qm', msg)


@pytest.fixture
def repo(tmp_path):
    """One `py10x` checkout committed on `main`: core at the root, both siblings under `cxx10x/`."""
    repo = tmp_path / 'py10x'
    _init(repo)
    _write(repo / KERNEL_DIR / 'pyproject.toml', '[project]\nname = "py10x-kernel"\ndependencies = ["uuid6>=2025.0.1"]\n')
    _write(repo / INFRA_DIR / 'pyproject.toml', '[project]\nname = "py10x-infra"\ndependencies = ["uuid6>=2025.0.1"]\n')
    _write(repo / 'cxx10x' / 'cmake' / 'shared.cmake', '# shared C++ build config\n')
    _write(
        repo / 'pyproject.toml',
        tomlkit.dumps(
            tomlkit.parse(
                '[project]\n'
                'name = "py10x-core"\n'
                'dependencies = [\n'
                f'    "py10x-kernel ({DEV_PIN})",\n'
                f'    "py10x-infra ({DEV_PIN})",\n'
                '    "numpy>=2.2.2,<2.5.0",\n'
                ']\n\n' + _siblings_toml()
            )
        ),
    )
    _commit_all(repo, 'init py10x')
    return repo


@pytest.fixture
def repo_with_downstream(repo):
    """`repo` plus an in-tree downstream (`xx_fin`, py10x-fin-base) pinning core."""
    _write(
        repo / 'xx_fin' / 'pyproject.toml',
        f'[project]\nname = "py10x-fin-base"\ndependencies = ["py10x-core ({DEV_PIN})", "uuid6>=2025.0.1"]\n',
    )
    doc = tomlkit.parse((repo / 'pyproject.toml').read_text(encoding='utf-8'))
    doc['tool']['dev_10x']['downstream'] = tomlkit.table()
    doc['tool']['dev_10x']['downstream']['py10x-fin-base'] = tomlkit.inline_table()
    doc['tool']['dev_10x']['downstream']['py10x-fin-base']['path'] = 'xx_fin'
    _write(repo / 'pyproject.toml', tomlkit.dumps(doc))
    _commit_all(repo, 'add fin-base')
    return repo


def _run_argv(argv):
    """Construct + verify + run, matching ``TraitableCli.main`` (skipping argv / exit-code)."""
    rc, inst = xp.XxPromoteCli.instance_from_args(argv)
    assert rc, rc.error() if not rc else ''
    if not (rc := inst.verify()):
        return rc
    return inst.run()


def _run(cmd, py_repo, *flags):
    out = _run_argv([cmd, '--base', str(py_repo), *flags])
    assert out, out.error() if not out else ''
    return out


def _run_pre(py_repo, *flags):
    _run('pre', py_repo, *flags)


def _run_prod(py_repo, *flags):
    _run('prod', py_repo, *flags)


def _change(repo, rel_path):
    _write(repo / rel_path, 'x = 1\n')
    _commit_all(repo, f'change {rel_path}')


def _change_kernel_source(repo, name):
    _change(repo, f'{KERNEL_DIR}/{name}')


def _dep_specs_at(repo, ref, rel_path):
    """{dep name: specifier str} from [project.dependencies] of `rel_path` at git `ref`."""
    doc = tomlkit.parse(GitHelpers.file_at_ref(repo, ref, rel_path))
    return {Requirement(str(e)).name: str(Requirement(str(e)).specifier) for e in doc['project']['dependencies']}


def _test_group_at(repo, ref, rel_path):
    doc = tomlkit.parse(GitHelpers.file_at_ref(repo, ref, rel_path))
    return list(doc.get('dependency-groups', {}).get('test', []))


def test_pre_from_main_cuts_coordinated_first_rc(repo):
    _run_pre(repo)

    # --- core: pre branch + tag, with exact forward == pins on both siblings ---
    assert set(GitHelpers.list_tags(repo, 'v*')) == {'v0.0.1rc1', 'v0.0.1rc2.dev'}
    assert GitHelpers.git(repo, 'rev-parse', 'pre') == GitHelpers.tag_commit(repo, 'v0.0.1rc1')
    main = GitHelpers.git(repo, 'rev-parse', 'main')
    assert GitHelpers.tag_commit(repo, 'v0.0.1rc2.dev') == main
    core_deps = _dep_specs_at(repo, 'v0.0.1rc1', 'pyproject.toml')
    assert core_deps['py10x-kernel'] == '==0.0.1rc1'
    assert core_deps['py10x-infra'] == '==0.0.1rc1'
    assert core_deps['numpy'] == '<2.5.0,>=2.2.2'  # untouched third-party dep

    # --- siblings: `pre-{name}` branch + tag on a release commit of its own; no reverse pin ---
    for name, sub in SIBLINGS:
        tag = f'{name}-v0.0.1rc1'
        assert set(GitHelpers.list_tags(repo, f'{name}-v*')) == {tag, f'{name}-v0.0.1rc2.dev'}
        assert GitHelpers.git(repo, 'rev-parse', f'pre-{name}') == GitHelpers.tag_commit(repo, tag)
        assert GitHelpers.tag_commit(repo, f'{name}-v0.0.1rc2.dev') == main
        # its own commit (never shared with another tag of the same train), forked off main
        assert GitHelpers.is_ancestor(repo, f'{tag}^', 'main')
        assert _test_group_at(repo, tag, f'{sub}/pyproject.toml') == []

    # --- the cut forks from main and leaves main + the working tree untouched ---
    assert GitHelpers.git(repo, 'rev-parse', '--abbrev-ref', 'HEAD') == 'main'
    assert GitHelpers.git(repo, 'status', '--porcelain') == ''
    fork = GitHelpers.git(repo, 'merge-base', 'main', 'pre')
    assert GitHelpers.is_ancestor(repo, fork, 'pre')
    # main epilogue: rc-window pins for the coordinated rc
    main_core = _dep_specs_at(repo, 'main', 'pyproject.toml')
    assert SpecifierSet(main_core['py10x-kernel']) == SpecifierSet(VersionHelpers.rc_window_pin('0.0.1rc1'))
    assert SpecifierSet(main_core['py10x-infra']) == SpecifierSet(VersionHelpers.rc_window_pin('0.0.1rc1'))


def test_pre_dry_run_is_side_effect_free(repo):
    """`--dry-run` must mutate nothing - in particular no getter (evaluated on the verify path)
    may switch branches. Run from a non-`main` branch and assert HEAD and tags are untouched."""
    GitHelpers.git(repo, 'checkout', '-q', '-b', 'feature')  # start off main
    _run_pre(repo, '--dry-run')
    assert GitHelpers.git(repo, 'rev-parse', '--abbrev-ref', 'HEAD') == 'feature'
    assert GitHelpers.list_tags(repo, '*') == []  # nothing cut
    assert GitHelpers.git(repo, 'branch', '--list', 'pre*') == ''
    assert GitHelpers.git(repo, 'status', '--porcelain') == ''


def test_pre_unchanged_packages_are_skipped(repo, capsys):
    """A second `pre` with no source changes re-cuts nothing and mints no new tags."""
    _run_pre(repo)
    capsys.readouterr()  # discard first-run completion hints
    tags = GitHelpers.list_tags(repo, '*')
    _run_pre(repo)  # nothing changed since the rc (only the epilogue touched main)
    assert GitHelpers.list_tags(repo, '*') == tags
    assert 'Local changes applied' not in capsys.readouterr().out


def test_core_only_change_does_not_recut_siblings(repo):
    """Core's Python and shared CI are outside the siblings' explicit footprints."""
    _run_pre(repo)
    _change(repo, 'core_10x/feature.py')
    _change(repo, '.github/workflows/ci.yml')
    _run_pre(repo)
    assert 'v0.0.1rc2' in GitHelpers.list_tags(repo, 'v*')
    for name, _sub in SIBLINGS:
        assert f'{name}-v0.0.1rc2' not in GitHelpers.list_tags(repo, f'{name}-v*')
    core_deps = _dep_specs_at(repo, 'v0.0.1rc2', 'pyproject.toml')
    assert core_deps['py10x-kernel'] == '==0.0.1rc1' and core_deps['py10x-infra'] == '==0.0.1rc1'


def test_shared_cxx_change_recuts_both_siblings(repo):
    """`cxx10x/cmake` is in both siblings' footprints but not core's: core re-cuts only via pin lag."""
    _run_pre(repo)
    _change(repo, 'cxx10x/cmake/shared.cmake')
    _run_pre(repo)
    for name, _sub in SIBLINGS:
        assert f'{name}-v0.0.1rc2' in GitHelpers.list_tags(repo, f'{name}-v*')
    core_deps = _dep_specs_at(repo, 'v0.0.1rc2', 'pyproject.toml')
    assert core_deps['py10x-kernel'] == '==0.0.1rc2' and core_deps['py10x-infra'] == '==0.0.1rc2'


def test_prod_stacks_final_on_rc_and_floors_main(repo):
    """prod promotes each rc: final stacked on the rc commit, exact `==` pins, main re-floored to dev."""
    _run_pre(repo)  # rc1 across the board
    _run_prod(repo)

    # --- core: prod branch + final tag, exact == on the released sibling finals ---
    assert 'v0.0.1' in GitHelpers.list_tags(repo, 'v*')
    assert GitHelpers.git(repo, 'rev-parse', 'prod') == GitHelpers.tag_commit(repo, 'v0.0.1')
    core_final = _dep_specs_at(repo, 'v0.0.1', 'pyproject.toml')
    assert core_final['py10x-kernel'] == '==0.0.1'
    assert core_final['py10x-infra'] == '==0.0.1'
    # released source == rc source: the final commit is stacked directly on the rc commit
    assert GitHelpers.git(repo, 'rev-parse', 'v0.0.1^') == GitHelpers.tag_commit(repo, 'v0.0.1rc1')

    # --- siblings: `prod-{name}` branch + final tag stacked on (not sharing) the rc commit ---
    for name, _sub in SIBLINGS:
        final = f'{name}-v0.0.1'
        assert final in GitHelpers.list_tags(repo, f'{name}-v*')
        assert GitHelpers.git(repo, 'rev-parse', f'prod-{name}') == GitHelpers.tag_commit(repo, final)
        assert GitHelpers.git(repo, 'rev-parse', f'{final}^') == GitHelpers.tag_commit(repo, f'{name}-v0.0.1rc1')

    # --- main epilogue: post-final window pins ---
    main_core = _dep_specs_at(repo, 'main', 'pyproject.toml')
    assert SpecifierSet(main_core['py10x-kernel']) == SpecifierSet(VersionHelpers.post_final_window_pin('0.0.1'))
    assert GitHelpers.git(repo, 'rev-parse', '--abbrev-ref', 'HEAD') == 'main'
    assert GitHelpers.git(repo, 'status', '--porcelain') == ''

    # --- main dev markers: rc-line replaced with post-final `{next_micro}rc0.dev` above the release ---
    assert GitHelpers.list_tags(repo, 'v*') == ['v0.0.1', 'v0.0.1rc1', 'v0.0.2rc0.dev']
    for name, _sub in SIBLINGS:
        assert GitHelpers.list_tags(repo, f'{name}-v*') == [f'{name}-v0.0.1', f'{name}-v0.0.1rc1', f'{name}-v0.0.2rc0.dev']
    assert set(GitHelpers.list_tags(repo, 'pre/*')) == {'pre/v0.0.1rc1', 'pre/py10x-kernel-v0.0.1rc1', 'pre/py10x-infra-v0.0.1rc1'}
    assert set(GitHelpers.list_tags(repo, 'prod/*')) == {'prod/v0.0.1', 'prod/py10x-kernel-v0.0.1', 'prod/py10x-infra-v0.0.1'}


def test_downstream_epilogues_do_not_trigger_recuts(repo_with_downstream, capsys):
    """Epilogue pin edits (core's test group, fin-base's core window) are not footprint changes."""
    repo = repo_with_downstream
    _run_pre(repo)
    assert 'py10x-fin-base-v0.0.1rc1' in GitHelpers.list_tags(repo, 'py10x-fin-base-v*')
    assert GitHelpers.git(repo, 'rev-parse', 'pre-py10x-fin-base') == GitHelpers.tag_commit(repo, 'py10x-fin-base-v0.0.1rc1')
    capsys.readouterr()
    tags = GitHelpers.list_tags(repo, '*')
    _run_pre(repo)
    assert GitHelpers.list_tags(repo, '*') == tags
    assert 'Local changes applied' not in capsys.readouterr().out


def test_pre_iterate_after_sibling_source_change_recoordinates(repo):
    """A kernel source change bumps kernel's rc and forces a core re-cut (pin lag); infra stays put."""
    _run_pre(repo)  # rc1 across the board

    _change_kernel_source(repo, 'feature.py')  # real kernel source change on main
    _run_pre(repo)

    assert 'py10x-kernel-v0.0.1rc2' in GitHelpers.list_tags(repo, 'py10x-kernel-v*')
    assert 'py10x-infra-v0.0.1rc2' not in GitHelpers.list_tags(repo, 'py10x-infra-v*')  # unchanged
    assert 'v0.0.1rc2' in GitHelpers.list_tags(repo, 'v*')  # core forced to re-cut by the stale pin

    core_deps = _dep_specs_at(repo, 'v0.0.1rc2', 'pyproject.toml')
    assert core_deps['py10x-kernel'] == '==0.0.1rc2'  # refreshed to the new kernel rc
    assert core_deps['py10x-infra'] == '==0.0.1rc1'  # infra unchanged -> its existing rc1
    # the new core rc forks from main, and the superseded rc1 survives only as its tag
    assert GitHelpers.git(repo, 'rev-parse', 'pre') == GitHelpers.tag_commit(repo, 'v0.0.1rc2')
    assert GitHelpers.tag_commit(repo, 'v0.0.1rc1') != GitHelpers.tag_commit(repo, 'v0.0.1rc2')


def _run_yank(py_repo, pkg, version, *flags):
    _run('yank', py_repo, '--pkg', pkg, '--version', version, *flags)


def test_yank_latest_rc_rolls_pre_back_and_consumes_the_number(repo):
    """Yank the latest kernel rc: tag renamed, pre rolled back to the prior rc, number not reused."""
    _run_pre(repo)  # rc1
    _change_kernel_source(repo, 'feature.py')
    _run_pre(repo)  # kernel rc2 (+ core rc2)
    rc1_commit = GitHelpers.tag_commit(repo, 'py10x-kernel-v0.0.1rc1')

    _run_yank(repo, 'py10x-kernel', '0.0.1rc2')

    live = GitHelpers.list_tags(repo, 'py10x-kernel-v0.0.1rc2')  # plain tag gone
    assert 'py10x-kernel-v0.0.1rc2' not in [t for t in live if not t.endswith('_yanked')]
    assert 'py10x-kernel-v0.0.1rc3.dev' in GitHelpers.list_tags(repo, 'py10x-kernel-v*')  # dev marker kept
    assert 'py10x-kernel-v0.0.1rc2_yanked' in GitHelpers.list_tags(repo, '*')
    # pointer rollback: pre-py10x-kernel reconciled to the previous (live) rc
    assert GitHelpers.git(repo, 'rev-parse', 'pre-py10x-kernel') == rc1_commit
    main_pins = _dep_specs_at(repo, 'main', 'pyproject.toml')
    assert SpecifierSet(main_pins['py10x-kernel']) == SpecifierSet(VersionHelpers.rc_window_pin('0.0.1rc1'))

    _change_kernel_source(repo, 'feature2.py')
    _run_pre(repo)
    # the yanked rc2 number is consumed: the next kernel rc is rc3, never a reused rc2
    assert 'py10x-kernel-v0.0.1rc3' in GitHelpers.list_tags(repo, 'py10x-kernel-v*')


def test_yank_non_latest_is_rejected_without_cascade(repo):
    """Stage 1 yanks the latest only; an older release is refused (cascade is Stage 2)."""
    _run_pre(repo)
    _change_kernel_source(repo, 'feature.py')
    _run_pre(repo)  # kernel now at rc2
    # post_verify refuses an older release, returning a falsy RC (no throw).
    out = _run_argv(['yank', '--pkg', 'py10x-kernel', '--version', '0.0.1rc1', '--base', str(repo)])
    assert not out and 'not the latest' in (out.error() or '')


@pytest.fixture
def remotes(tmp_path, repo):
    """Add a bare `origin` remote and seed `main`. Returns (repo, remote)."""
    remote = tmp_path / 'py10x.git'
    GitHelpers.git(tmp_path, 'init', '--bare', '-q', str(remote))
    GitHelpers.git(repo, 'remote', 'add', 'origin', str(remote))
    GitHelpers.git(repo, 'push', '-q', 'origin', 'main')
    return repo, remote


def _remote_tags(remote) -> set[str]:
    return set(GitHelpers.git(remote, 'tag', '--list').split())


def test_resync_does_not_print_promote_completion_hints(remotes, capsys):
    """resync resets local refs to origin — not an unpushed promote; no promote-style footer."""
    repo, _remote = remotes
    _run_pre(repo)  # local-only cut gives resync something to reset
    capsys.readouterr()  # discard pre's promote footer
    _run_argv(['resync', '--base', str(repo)])
    out = capsys.readouterr().out
    assert 'reset-local' in out
    assert 'Local changes applied' not in out
    assert 'Refs pushed' not in out


def test_local_promote_work_requires_resync(remotes):
    """A promote run (even without --push) mutates main via the epilogue (pins + dev marker).
    A follow-up promote therefore fails require_synced on main (not just tags).
    Explicit resync is still the way to discard local work and get back to origin."""
    repo, remote = remotes
    _run_pre(repo)  # cut rc1 LOCALLY (no --push)
    assert 'v0.0.1rc1' in GitHelpers.list_tags(repo, 'v*')
    assert GitHelpers.git(remote, 'tag', '--list') == ''

    out = _run_argv(['pre', '--base', str(repo), '--push'])
    assert not out and 'origin/main' in (out.error() or '')  # main was advanced locally by the first promote

    _run('resync', repo)  # discard local work (main + tags + branches)
    assert GitHelpers.list_tags(repo, 'v*') == [] and GitHelpers.list_tags(repo, 'py10x-kernel-v*') == []
    for branch in ('pre', 'pre-py10x-kernel', 'pre-py10x-infra'):
        assert GitHelpers.git(repo, 'rev-parse', '--verify', '--quiet', branch, check=False) == ''

    _run_pre(repo, '--push')  # now clean; succeeds and pushes
    assert 'v0.0.1rc1' in _remote_tags(remote)


def test_pre_push_is_one_atomic_push_plus_triggers(remotes, monkeypatch):
    """One repo: every package's branch/tag/marker and the main epilogue land in a single atomic
    push - a partial cross-package push is unreachable. Publish triggers are pushed one at a time."""
    repo, _remote = remotes
    pushes: list[list[str]] = []
    orig_git = GitHelpers.git

    def tracking_git(r, *args, check=True):
        if args and args[0] == 'push' and '--atomic' in args:
            pushes.append([a for a in args if a not in ('push', '--atomic', 'origin', '-q')])
        return orig_git(r, *args, check=check)

    monkeypatch.setattr(GitHelpers, 'git', staticmethod(tracking_git))
    _run_pre(repo, '--push')

    triggers = [p for p in pushes if any(r.startswith(('pre/', 'prod/')) for r in p)]
    refs = [p for p in pushes if p not in triggers]
    assert len(triggers) == 3  # core + kernel + infra, one push each
    assert all(sum(r.startswith(('pre/', 'prod/')) for r in p) == 1 for p in triggers)
    assert not any(r.startswith(':refs/') for p in triggers for r in p)
    assert len(refs) == 1
    assert {'+pre', '+pre-py10x-kernel', '+pre-py10x-infra', 'v0.0.1rc1', 'py10x-kernel-v0.0.1rc1', 'py10x-infra-v0.0.1rc1'} <= set(refs[0])


def test_pre_push_lands_tags_and_force_resets_branches_on_remote(remotes):
    repo, remote = remotes

    _run_pre(repo, '--push')

    assert {'v0.0.1rc1', 'v0.0.1rc2.dev', 'pre/v0.0.1rc1', 'pre/py10x-kernel-v0.0.1rc1'} <= _remote_tags(remote)
    assert sorted(GitHelpers.git(remote, 'branch', '--list', '--format=%(refname:short)').split()) == [
        'main',
        'pre',
        'pre-py10x-infra',
        'pre-py10x-kernel',
    ]
    assert GitHelpers.git(remote, 'rev-parse', 'pre') == GitHelpers.tag_commit(repo, 'v0.0.1rc1')

    # a second cut force-resets the remote pre branch (non-ff) to the new rc. main must be pushed
    # first (the start invariant: local==remote), then the cut finishes with local==remote again.
    _change(repo, 'src.py')
    GitHelpers.git(repo, 'push', '-q', 'origin', 'main')
    _run_pre(repo, '--push')
    tags = _remote_tags(remote)
    assert 'v0.0.1rc2' in tags and 'pre/v0.0.1rc2' in tags and 'pre/v0.0.1rc1' not in tags
    assert GitHelpers.git(remote, 'rev-parse', 'pre') == GitHelpers.tag_commit(repo, 'v0.0.1rc2')
    # finish invariant: local == remote (tags + pre branch)
    assert set(GitHelpers.git(repo, 'tag', '--list').split()) == tags
    assert GitHelpers.git(repo, 'rev-parse', 'pre') == GitHelpers.git(remote, 'rev-parse', 'pre')


def _delete_remote_triggers(repo, flavor: str):
    for tag in GitHelpers.ls_remote_tags(repo, f'{flavor}/*'):
        GitHelpers.git(repo, 'push', '--atomic', 'origin', f':refs/tags/{tag}')


def test_pre_publish_recreates_triggers_after_resync(remotes):
    """Crash recovery: resync drops local-only triggers, then `pre --publish-only --push` recreates them."""
    repo, remote = remotes
    _run_pre(repo, '--push')
    _delete_remote_triggers(repo, 'pre')
    _run('resync', repo)
    out = _run_argv(['pre', '--publish-only', '--base', str(repo), '--push'])
    assert out, out.error() if not out else ''
    assert {'pre/v0.0.1rc1', 'pre/py10x-kernel-v0.0.1rc1', 'pre/py10x-infra-v0.0.1rc1'} <= _remote_tags(remote)


def test_pre_publish_refuses_existing_triggers(remotes, capsys):
    repo, _remote = remotes
    _run_pre(repo, '--push')
    out = _run_argv(['pre', '--publish-only', '--base', str(repo), '--push'])
    assert out, out.error() if not out else ''
    assert 'already present' in capsys.readouterr().out


def test_pre_no_publish_then_publish_only(remotes):
    """Cut and push without triggers, then attach triggers in a second step."""
    repo, remote = remotes
    _run_pre(repo, '--push', '--no-publish')
    assert not any(t.startswith('pre/') for t in _remote_tags(remote))
    assert 'v0.0.1rc1' in _remote_tags(remote)
    _run_argv(['pre', '--publish-only', '--base', str(repo), '--push'])
    assert 'pre/v0.0.1rc1' in _remote_tags(remote)


def test_promote_refuses_unsynced_main(remotes):
    """Start invariant: an un-pushed `main` is refused (local != origin/main) and nothing is cut."""
    repo, remote = remotes
    _change(repo, 'src.py')  # NOT pushed to origin
    rc = _run_argv(['pre', '--base', str(repo), '--push'])  # post_verify refuses (returns RC)
    assert not rc and 'origin/main' in (rc.error() or '')
    assert GitHelpers.git(remote, 'tag', '--list') == ''  # nothing cut/pushed


def test_yank_push_rolls_remote_pre_back(remotes):
    """yank --push: the remote tag is renamed and the remote `pre-{name}` branch rolled back (local==remote)."""
    repo, _remote = remotes
    _run_pre(repo, '--push')  # rc1
    _change_kernel_source(repo, 'feature.py')
    GitHelpers.git(repo, 'push', '-q', 'origin', 'main')
    _run_pre(repo, '--push')  # kernel rc2
    rc1_commit = GitHelpers.tag_commit(repo, 'py10x-kernel-v0.0.1rc1')

    _run_yank(repo, 'py10x-kernel', '0.0.1rc2', '--push')

    live = GitHelpers.ls_remote_tags(repo, 'py10x-kernel-v*')
    assert 'py10x-kernel-v0.0.1rc2' not in live and 'py10x-kernel-v0.0.1rc2_yanked' in live
    assert GitHelpers.ls_remote_ref(repo, 'refs/heads/pre-py10x-kernel') == rc1_commit
    assert GitHelpers.git(repo, 'rev-parse', 'pre-py10x-kernel') == rc1_commit


def test_someone_else_promoted_stale_dev_new_tags_pyproject_change(remotes, capsys):
    """When someone else promotes (new release tags, stale dev markers deleted on remote + pyproject
    epilogue commit on main), a local clone that hasn't pulled will fail require_synced on the main
    rev check (require_clean does *not* fail on tag mismatch; it only checks working tree).

    After `git pull`, main matches; the tag reconciliation in require_synced cleans stale local
    dev tags and fetches missing new release tags, allowing the promote command to succeed.

    This is the realistic "someone else promoted while you were behind" scenario.
    """
    py, _remote = remotes

    # Pre-create a dev marker tag that the promote will treat as stale (will be deleted during promote)
    stale_dev = 'v0.0.1rc0.dev'
    GitHelpers.git(py, 'tag', stale_dev, 'main')
    GitHelpers.git(py, 'push', '-q', 'origin', f'refs/tags/{stale_dev}')

    # Local change so the promote has a footprint change and will write epilogue (pyproject update on main)
    _write(py / 'src.py', 'x = 1\n')
    GitHelpers.git(py, 'add', '.')
    GitHelpers.git(py, 'commit', '-qm', 'change before promote')

    # Push the change commit so the upcoming promote's require_synced sees local main == origin/main
    GitHelpers.git(py, 'push', '-q', 'origin', 'main')
    old_main = GitHelpers.git(py, 'rev-parse', 'main')

    # "Someone else" promotes: this does the epilogue commit on main (pyproject pin changes),
    # creates new release tag + new dev marker, deletes stale_dev locally+pushes delete ref.
    _run_pre(py, '--push')

    # Simulate your local not having pulled the advance:
    GitHelpers.git(py, 'reset', '--hard', old_main)

    # Re-create the now-stale dev tag locally (remote no longer has it)
    GitHelpers.git(py, 'tag', stale_dev, old_main)

    # First attempt: fails because local main (old) != origin/main (the epilogue commit)
    # Tag reconciliation code is not reached (main check is before it).
    # require_clean did not crash (tag mismatch alone does not make tree dirty).
    # (Note: the fetch inside this call will prune-tags the stale and bring new tags.)
    out = _run_argv(['pre', '--base', str(py), '--push'])
    assert not out
    assert 'local main != origin/main' in (out.error() or '')

    # Re-create stale *after* the fetch that happened in the failing call (so reconcile on next will see it)
    GitHelpers.git(py, 'tag', stale_dev, old_main)

    # Remove the new release tag locally (it was brought by the previous fetch) so the *next* reconcile fetches it
    new_release = 'v0.0.1rc1'
    if new_release in GitHelpers.list_tags(py, 'v*'):
        GitHelpers.git(py, 'tag', '-d', new_release)

    # Now pull (catch up on the main commit with pyproject changes)
    GitHelpers.git(py, 'pull', '-q', 'origin', 'main')

    # Second attempt: main now matches. require_synced runs tag reconciliation:
    # - deletes the stale_dev (only_local)
    # - fetches the missing new_release (only_remote)
    # Succeeds (no error from require_synced).
    out = _run_argv(['pre', '--base', str(py), '--push'])
    assert out, out.error() if not out else ''

    # Reconciliation (and/or prune-tags + tag fetch in require_synced) effects visible after pull + successful require
    assert stale_dev not in GitHelpers.list_tags(py, 'v*')
    assert new_release in GitHelpers.list_tags(py, 'v*')
    # (The 'cleaned stale...' print may or may not appear depending on timing with --prune-tags fetch.)
