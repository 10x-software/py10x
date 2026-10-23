"""CLI/subprocess-orchestration tests for `xx-functional-account-init`
(`FunctionalAccountInitCli`). Docker and the provisioning command are both mocked -- this exercises
argv construction, image/docker-arg auto-resolution, the FIFO-transport reader thread, and error
propagation, not a real container. See `core_10x/unit_tests/test_functional_account_vault.py` for
the real-container end-to-end path and `docs/VAULT_SECURITY_DESIGN.md` §3.3 for the design."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import textwrap
import threading

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


def _fifo_paths(argv: list[str]) -> tuple[str, str]:
    mount = argv[argv.index('-v') + 1]
    host_dir, _sep, _container_dir = mount.partition(':')
    output = argv[argv.index('--output-file') + 1]
    return host_dir, os.path.join(host_dir, os.path.basename(output))


def _assert_fifo_is_owner_write_only(argv: list[str]) -> None:
    """By `docker run` the host holds the read fd. The pipe is owner-write only, so a new
    open for reading fails even for the owner. The directory is traversable by the container
    uid and not listable or writable by other. 0600/0700 and 0622 both fail this."""
    host_dir, fifo_path = _fifo_paths(argv)
    assert os.stat(host_dir).st_mode & 0o777 == 0o711
    assert stat.S_ISFIFO(os.stat(fifo_path).st_mode)
    assert os.stat(fifo_path).st_mode & 0o777 == 0o200
    with pytest.raises(PermissionError):
        os.open(fifo_path, os.O_RDONLY | os.O_NONBLOCK)


def _write_fifo_from_fake_docker(argv: list[str], payload: str, *, delay_s: float = 0) -> None:
    """Simulate the container side of a `docker run ... xx-user-init --functional-account
    --output-file <path>` invocation: find the bind mount from `-v host:container` and write
    directly to the host-side path, exactly what the real container would produce via the mount."""
    _assert_fifo_is_owner_write_only(argv)
    _host_dir, fifo_path = _fifo_paths(argv)
    if delay_s:
        import time

        time.sleep(delay_s)
    # 'w' is O_WRONLY|O_CREAT|O_TRUNC. Mode 0200 allows the owner write and refuses a read.
    with open(fifo_path, 'w') as f:
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
    assert argv[-4:] == ['xx-user-init', '--functional-account', '--output-file', '/var/run/xx-provisioning-output/xx-myservice.fifo']
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
            # container fails before ever writing the fifo; perms are already those it would have seen
            _assert_fifo_is_owner_write_only(argv)
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


def test_run_reads_manifest_when_the_container_writes_late(monkeypatch):
    """A nonblocking read returns b'' before any writer opens. That must not end the read."""
    monkeypatch.setattr(EnvVars, 'main_vault_uri', 'postgresql://vault-host.example.com:5432/vaultdb')
    monkeypatch.setattr(FunctionalAccountInitCli, '_resolve_image', lambda self: (RC_TRUE, 'fake-image:dev'))
    payload = json.dumps([{'service': 's', 'username': 'u', 'password': 'p'}])
    seen = {}

    def fake_run(argv, **kwargs):
        if argv[:2] == ['docker', 'run']:
            _write_fifo_from_fake_docker(argv, payload, delay_s=0.3)
            return subprocess.CompletedProcess(argv, 0)
        seen['provisioning_input'] = kwargs.get('input')
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr('core_10x.apps.functional_account_init.subprocess.run', fake_run)
    _rc, inst = FunctionalAccountInitCli.instance_from_args(['--functional-account-id', 'xx-myservice', '--command', 'cat'])
    result = inst.run()
    assert result, result.error()
    assert seen['provisioning_input'] == payload


def test_run_drains_fifo_while_the_container_writes(monkeypatch):
    """Pipe capacity is configurable and can be one page. The reader has to drain during the write."""
    monkeypatch.setattr(EnvVars, 'main_vault_uri', 'postgresql://vault-host.example.com:5432/vaultdb')
    monkeypatch.setattr(FunctionalAccountInitCli, '_resolve_image', lambda self: (RC_TRUE, 'fake-image:dev'))
    payload = 'x' * (1024 * 1024)
    seen = {}
    wrote = threading.Event()

    def fake_run(argv, **kwargs):
        if argv[:2] == ['docker', 'run']:
            _assert_fifo_is_owner_write_only(argv)

            def _write():
                _host_dir, fifo_path = _fifo_paths(argv)
                with open(fifo_path, 'w') as f:
                    f.write(payload)
                wrote.set()

            threading.Thread(target=_write, daemon=True).start()
            assert wrote.wait(5), 'reader did not drain the FIFO; a full pipe would stall docker run'
            return subprocess.CompletedProcess(argv, 0)
        seen['provisioning_input'] = kwargs.get('input')
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr('core_10x.apps.functional_account_init.subprocess.run', fake_run)
    _rc, inst = FunctionalAccountInitCli.instance_from_args(['--functional-account-id', 'xx-myservice', '--command', 'cat'])
    result = inst.run()
    assert result, result.error()
    assert seen['provisioning_input'] == payload


def _entrypoint_path() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'docker', 'entrypoint.sh'))


def _stub_bin(tmp_path):
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    for name, body in {
        'id': textwrap.dedent(
            """\
            #!/bin/sh
            printf '%s\\n' "id $*" >> "$STUB_LOG"
            case "$1" in
              -u) echo 10001 ;;
              -g) echo 10001 ;;
            esac
            exit 0
            """
        ),
        'usermod': '#!/bin/sh\nprintf \'%s\\n\' "usermod $*" >> "$STUB_LOG"\nexit 0\n',
        'groupmod': '#!/bin/sh\nprintf \'%s\\n\' "groupmod $*" >> "$STUB_LOG"\nexit 0\n',
        'chown': '#!/bin/sh\nprintf \'%s\\n\' "chown $*" >> "$STUB_LOG"\nexit 0\n',
        'gosu': '#!/bin/sh\nprintf \'%s\\n\' "gosu $*" >> "$STUB_LOG"\nexit 0\n',
    }.items():
        path = bindir / name
        path.write_text(body)
        path.chmod(0o755)
    return bindir


def _run_entrypoint(tmp_path, provisioning_dir: str | None):
    log_path = tmp_path / 'stub.log'
    log_path.write_text('')
    env = os.environ.copy()
    env['PATH'] = f'{_stub_bin(tmp_path)}:{env["PATH"]}'
    env['STUB_LOG'] = str(log_path)
    env['FUNCTIONAL_ACCOUNT_ID'] = 'xx-myservice'
    env.pop('XX_SECRETS_DIR', None)
    if provisioning_dir is None:
        env.pop('XX_PROVISIONING_OUTPUT_DIR', None)
        missing = tmp_path / 'no-such-provisioning-dir'
        env['XX_PROVISIONING_OUTPUT_DIR'] = str(missing)
    else:
        env['XX_PROVISIONING_OUTPUT_DIR'] = provisioning_dir
    completed = subprocess.run(['bash', _entrypoint_path()], env=env, capture_output=True, text=True, check=False)
    log = log_path.read_text()
    assert completed.returncode == 0, completed.stderr
    return log


def test_entrypoint_chowns_provisioning_fifo_before_gosu(tmp_path):
    provisioning = tmp_path / 'out'
    provisioning.mkdir()
    os.mkfifo(provisioning / 'xx-myservice.fifo', 0o200)
    log = _run_entrypoint(tmp_path, str(provisioning))
    chown_at = log.index('chown ')
    gosu_at = log.index('gosu ')
    assert chown_at < gosu_at
    assert f'chown 10001:10001 {provisioning / "xx-myservice.fifo"}' in log
    assert 'gosu xx-myservice' in log


def test_entrypoint_skips_chown_without_provisioning_dir(tmp_path):
    log = _run_entrypoint(tmp_path, None)
    assert 'chown ' not in log
    assert 'gosu xx-myservice' in log
