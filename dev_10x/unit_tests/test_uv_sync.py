"""`uv-sync py10x-dev`: a thin wrapper over `./xx-build` (install mode -> build mode, args -> groups)."""

from __future__ import annotations

from pathlib import Path

import pytest

from dev_10x import uv_sync


def _command(monkeypatch, tmp_path, *args, mode=None, venv=True):
    if mode is None:
        monkeypatch.delenv('XX_UV_INSTALL_MODE', raising=False)
    else:
        monkeypatch.setenv('XX_UV_INSTALL_MODE', mode)
    if venv:
        (tmp_path / '.venv').mkdir(exist_ok=True)
    return uv_sync.xx_build_command(args, root=tmp_path)


def _after_xx_build(cmd: list[str]) -> list[str]:
    assert cmd[: len(uv_sync.XX_BUILD)] == uv_sync.XX_BUILD
    return cmd[len(uv_sync.XX_BUILD) :]


def test_runs_the_same_command_as_the_xx_build_script():
    script = (Path(uv_sync.__file__).resolve().parents[1] / 'xx-build').read_text(encoding='utf-8')
    assert f'exec {" ".join(uv_sync.XX_BUILD)} "$@"' in script


@pytest.mark.parametrize(
    ('install_mode', 'build_mode'),
    [(None, 'dev'), ('incremental_quiet', 'dev'), ('incremental', 'dev'), ('editable', 'ci-release'), ('normal', 'ci-release')],
)
def test_install_mode_maps_to_build_mode(monkeypatch, tmp_path, install_mode, build_mode):
    cmd = _after_xx_build(_command(monkeypatch, tmp_path, '--all-extras', '--with-downstream', mode=install_mode))
    assert cmd == ['set-mode', build_mode]


def test_rejects_an_unknown_install_mode(monkeypatch, tmp_path):
    with pytest.raises(ValueError, match='XX_UV_INSTALL_MODE'):
        _command(monkeypatch, tmp_path, mode='bogus')


def test_without_downstream_leaves_fin_base_out(monkeypatch, tmp_path):
    """Core CI asserts xxfin is not importable before its suite."""
    cmd = _after_xx_build(_command(monkeypatch, tmp_path, '--all-extras'))
    assert cmd == ['set-mode', 'dev', '--no-group', 'test', '--no-group', 'test-extras']


def test_without_all_extras_leaves_core_extras_out(monkeypatch, tmp_path):
    cmd = _after_xx_build(_command(monkeypatch, tmp_path, '--with-downstream'))
    assert cmd == ['set-mode', 'dev', '--no-group', 'extras']


def test_downstream_names_are_ignored_and_other_args_passed_on(monkeypatch, tmp_path):
    cmd = _after_xx_build(_command(monkeypatch, tmp_path, '--with-downstream', 'py10x-fin-base', '--all-extras', '--locked', '--upgrade'))
    assert cmd == ['set-mode', 'dev', '--locked']  # --upgrade dropped


def test_no_venv_yet_runs_init(monkeypatch, tmp_path):
    cmd = _after_xx_build(_command(monkeypatch, tmp_path, '--all-extras', '--with-downstream', mode='editable', venv=False))
    assert cmd == ['init', '--mode', 'ci-release']


@pytest.mark.parametrize('profile', ['user', 'domain-dev', 'bogus'])
def test_only_the_dev_profile_remains(profile, capsys):
    assert uv_sync.main([profile]) == 2
    assert 'Usage' in capsys.readouterr().err


def test_runs_xx_build_and_returns_its_exit_code(monkeypatch, tmp_path):
    runs = []

    class Done:
        returncode = 3

    monkeypatch.setattr(uv_sync, 'PROJECT_ROOT', tmp_path)
    monkeypatch.setattr(uv_sync.subprocess, 'run', lambda cmd, **kw: runs.append(cmd) or Done())
    monkeypatch.delenv('XX_UV_INSTALL_MODE', raising=False)
    (tmp_path / '.venv').mkdir()
    assert uv_sync.main(['py10x-dev', '--all-extras', '--with-downstream']) == 3
    assert runs == [[*uv_sync.XX_BUILD, 'set-mode', 'dev']]


def test_parse_with_downstream():
    assert uv_sync._parse_with_downstream(('--with-downstream', 'a', 'b', '--x')) == (True, {'a', 'b'}, ['--x'])
    assert uv_sync._parse_with_downstream(('--x',)) == (False, None, ['--x'])
