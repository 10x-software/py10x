"""CLI/subprocess-orchestration tests for `xx-functional-account-init`
(`FunctionalAccountInitCli`). Docker and the provisioning command are both mocked -- this exercises
argv construction, image/docker-arg auto-resolution, the FIFO-transport reader thread, and error
propagation, not a real container. See `core_10x/unit_tests/test_functional_account_vault.py` for
the real-container end-to-end path and `docs/VAULT_SECURITY_DESIGN.md` §3.3 for the design."""

from __future__ import annotations

import json
import os
import sys

import pytest
from core_10x.apps.functional_account_init import FunctionalAccountInitCli
from core_10x.environment_variables import EnvVars
from core_10x.rc import RC, RC_TRUE

pytestmark = pytest.mark.skipif(
    sys.platform == 'win32',
    reason='xx-functional-account-init wraps `docker run`; not exercised on Windows',
)


def _run(monkeypatch, argv):
    monkeypatch.setattr(sys, 'argv', argv)
    return FunctionalAccountInitCli.main()


def _write_fifo_from_fake_docker(argv: list[str], payload: str) -> None:
    """Simulate the container side of a `docker run ... xx-user-init --functional-account
    --output-file <path>` invocation: find the bind mount from `-v host:container` and write
    directly to the host-side path, exactly what the real container would produce via the mount."""
    mount = argv[argv.index('-v') + 1]
    host_dir, _sep, _container_dir = mount.partition(':')
    with open(os.path.join(host_dir, 'manifest.fifo'), 'w') as f:
        f.write(payload)


def test_functional_account_id_is_required(monkeypatch, capsys):
    argv = ['xx-functional-account-init', '--command', 'echo hi']
    assert _run(monkeypatch, argv) == 1
    assert '--functional-account-id is required' in capsys.readouterr().out


def test_command_is_required(monkeypatch, capsys):
    argv = ['xx-functional-account-init', '--functional-account-id', 'xx-myservice']
    assert _run(monkeypatch, argv) == 1
    assert '--command is required' in capsys.readouterr().out


def test_rejects_non_prefixed_account_id(monkeypatch, capsys):
    argv = ['xx-functional-account-init', '--functional-account-id', 'not-prefixed', '--command', 'echo hi']
    assert _run(monkeypatch, argv) == 1
    assert 'must start with the functional-account prefix' in capsys.readouterr().out


def test_resolve_docker_args_requires_main_vault_uri(monkeypatch):
    monkeypatch.setattr(EnvVars, 'main_vault_uri', '')
    rc, inst = FunctionalAccountInitCli.instance_from_args(['--functional-account-id', 'xx-myservice', '--command', 'echo hi'])
    assert rc
    rc, _args = inst._resolve_docker_args()
    assert not rc
    assert 'XX_MAIN_VAULT_URI must be set' in rc.error()


def test_resolve_docker_args_adds_network_host_for_loopback_vault(monkeypatch):
    monkeypatch.setattr(EnvVars, 'main_vault_uri', 'postgresql://localhost:5432/vaultdb')
    rc, inst = FunctionalAccountInitCli.instance_from_args(['--functional-account-id', 'xx-myservice', '--command', 'echo hi'])
    rc, args = inst._resolve_docker_args()
    assert rc
    assert '-e' in args and 'XX_MAIN_VAULT_URI=postgresql://localhost:5432/vaultdb' in args
    assert '--network' in args and 'host' in args


def test_resolve_docker_args_skips_network_host_for_remote_vault(monkeypatch):
    monkeypatch.setattr(EnvVars, 'main_vault_uri', 'postgresql://vault-host.example.com:5432/vaultdb')
    rc, inst = FunctionalAccountInitCli.instance_from_args(['--functional-account-id', 'xx-myservice', '--command', 'echo hi'])
    rc, args = inst._resolve_docker_args()
    assert rc
    assert '--network' not in args


def test_resolve_docker_args_appends_extra_args(monkeypatch):
    # The value must not itself start with "--": TraitableCli.parse()'s simple
    # option-vs-value heuristic (a following "--"-prefixed token is treated as the *next*
    # option, not this one's value) can't tell the two apart otherwise -- a pre-existing
    # framework parsing limitation, not something this CLI works around.
    monkeypatch.setattr(EnvVars, 'main_vault_uri', 'postgresql://vault-host.example.com:5432/vaultdb')
    rc, inst = FunctionalAccountInitCli.instance_from_args(
        [
            '--functional-account-id',
            'xx-myservice',
            '--command',
            'echo hi',
            '--extra-docker-args',
            'label owner=infra',
        ]
    )
    rc, args = inst._resolve_docker_args()
    assert rc
    assert args[-2:] == ['label', 'owner=infra']


def test_image_tag_override_skips_auto_detection(monkeypatch):
    monkeypatch.setattr(
        'core_10x.apps.functional_account_init.subprocess.run',
        lambda *a, **k: (_ for _ in ()).throw(AssertionError('docker manifest inspect must not run when --image-tag is given')),
    )
    rc, inst = FunctionalAccountInitCli.instance_from_args(['--functional-account-id', 'xx-myservice', '--command', 'echo hi', '--image-tag', 'dev'])
    rc, image = inst._resolve_image()
    assert rc
    assert image == 'ghcr.io/10x-software/py10x-core:dev'


def test_image_auto_detection_failure_names_fallback(monkeypatch):
    import subprocess

    def fake_run(argv, **kwargs):
        assert argv[:3] == ['docker', 'manifest', 'inspect']
        return subprocess.CompletedProcess(argv, 1)

    monkeypatch.setattr('core_10x.apps.functional_account_init.subprocess.run', fake_run)
    rc, inst = FunctionalAccountInitCli.instance_from_args(['--functional-account-id', 'xx-myservice', '--command', 'echo hi'])
    rc, _image = inst._resolve_image()
    assert not rc
    assert '--image-tag dev|pre|prod|<tag>' in rc.error()


def test_run_wires_functional_account_id_and_output_file_into_docker_argv(monkeypatch, tmp_path):
    import subprocess

    monkeypatch.setattr(EnvVars, 'main_vault_uri', 'postgresql://vault-host.example.com:5432/vaultdb')
    monkeypatch.setattr(FunctionalAccountInitCli, '_resolve_image', lambda self: (RC_TRUE, 'fake-image:dev'))

    seen = {}
    real_run = subprocess.run

    def fake_run(argv, **kwargs):
        if argv[:2] == ['docker', 'run']:
            seen['docker_argv'] = argv
            _write_fifo_from_fake_docker(argv, json.dumps([{'service': 's', 'username': 'u', 'password': 'p'}]))
            return subprocess.CompletedProcess(argv, 0)
        seen['provisioning_argv'] = argv
        seen['provisioning_input'] = kwargs.get('input')
        return real_run(argv, **kwargs)

    monkeypatch.setattr('core_10x.apps.functional_account_init.subprocess.run', fake_run)

    _rc, inst = FunctionalAccountInitCli.instance_from_args(['--functional-account-id', 'xx-myservice', '--command', 'cat'])
    result = inst.run()
    assert result, result.error()

    argv = seen['docker_argv']
    assert '-e' in argv and 'FUNCTIONAL_ACCOUNT_ID=xx-myservice' in argv
    assert argv[-4:] == ['xx-user-init', '--functional-account', '--output-file', '/var/run/xx-provisioning-output/manifest.fifo']
    assert 'fake-image:dev' in argv
    assert seen['provisioning_input'] == json.dumps([{'service': 's', 'username': 'u', 'password': 'p'}])


def test_run_quotes_secret_name_against_command_splintering(monkeypatch):
    """Mirrors test_user_init.py's equivalent -- {secret_name} must stay one token even for a
    hostile account id, reusing the same shlex.quote-based templating as UserInitCli."""
    import subprocess

    hostile_id = 'xx-evil; rm -rf /'
    monkeypatch.setattr(EnvVars, 'main_vault_uri', 'postgresql://vault-host.example.com:5432/vaultdb')
    monkeypatch.setattr(FunctionalAccountInitCli, '_resolve_image', lambda self: (RC_TRUE, 'fake-image:dev'))

    seen_argv: list[str] = []

    def fake_run(argv, **kwargs):
        if argv[:2] == ['docker', 'run']:
            _write_fifo_from_fake_docker(argv, '[]')
            return subprocess.CompletedProcess(argv, 0)
        seen_argv.extend(argv)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr('core_10x.apps.functional_account_init.subprocess.run', fake_run)

    _rc, inst = FunctionalAccountInitCli.instance_from_args(['--functional-account-id', hostile_id, '--command', 'echo {secret_name} extra'])
    result = inst.run()
    assert result, result.error()
    assert seen_argv == ['echo', f'{hostile_id}-vault-keyring', 'extra']


def test_run_reports_docker_failure_and_cleans_up(monkeypatch):
    import subprocess

    monkeypatch.setattr(EnvVars, 'main_vault_uri', 'postgresql://vault-host.example.com:5432/vaultdb')
    monkeypatch.setattr(FunctionalAccountInitCli, '_resolve_image', lambda self: (RC_TRUE, 'fake-image:dev'))

    tmp_dirs = []
    import tempfile

    real_mkdtemp = tempfile.mkdtemp

    def tracking_mkdtemp(*a, **k):
        d = real_mkdtemp(*a, **k)
        tmp_dirs.append(d)
        return d

    def fake_run(argv, **kwargs):
        if argv[:2] == ['docker', 'run']:
            # container fails before ever writing the fifo
            return subprocess.CompletedProcess(argv, 1)
        raise AssertionError('provisioning command must not run when docker run fails')

    monkeypatch.setattr('core_10x.apps.functional_account_init.subprocess.run', fake_run)
    monkeypatch.setattr('core_10x.apps.functional_account_init.tempfile.mkdtemp', tracking_mkdtemp)

    _rc, inst = FunctionalAccountInitCli.instance_from_args(['--functional-account-id', 'xx-myservice', '--command', 'echo hi'])
    result = inst.run()
    assert not result
    assert 'docker run failed' in result.error()
    assert tmp_dirs and not os.path.exists(tmp_dirs[0])


def test_run_reports_provisioning_command_failure_and_cleans_up(monkeypatch):
    import subprocess
    import tempfile

    monkeypatch.setattr(EnvVars, 'main_vault_uri', 'postgresql://vault-host.example.com:5432/vaultdb')
    monkeypatch.setattr(FunctionalAccountInitCli, '_resolve_image', lambda self: (RC_TRUE, 'fake-image:dev'))

    tmp_dirs = []
    real_mkdtemp = tempfile.mkdtemp

    def tracking_mkdtemp(*a, **k):
        d = real_mkdtemp(*a, **k)
        tmp_dirs.append(d)
        return d

    def fake_run(argv, **kwargs):
        if argv[:2] == ['docker', 'run']:
            _write_fifo_from_fake_docker(argv, '[]')
            return subprocess.CompletedProcess(argv, 0)
        raise subprocess.CalledProcessError(1, argv)

    monkeypatch.setattr('core_10x.apps.functional_account_init.subprocess.run', fake_run)
    monkeypatch.setattr('core_10x.apps.functional_account_init.tempfile.mkdtemp', tracking_mkdtemp)

    _rc, inst = FunctionalAccountInitCli.instance_from_args(['--functional-account-id', 'xx-myservice', '--command', 'false'])
    result = inst.run()
    assert not result
    assert '--command failed' in result.error()
    assert tmp_dirs and not os.path.exists(tmp_dirs[0])
