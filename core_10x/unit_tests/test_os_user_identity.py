"""`OsUser.me.name()` (`cxx10x/core_10x/os_user.cpp`) is a C++ singleton that caches its resolved
name for the life of the process -- a single pytest process can't exercise more than one scenario
in-process, so each runs in its own subprocess. See docs/VAULT_SECURITY_DESIGN.md §3.3: every
identity, including functional accounts, must match the real, kernel-verified
`getpwuid(geteuid())` identity.
"""

import getpass
import os
import subprocess
import sys

_CODE = 'import core_10x\nfrom py10x_kernel import OsUser\nprint(OsUser.me.name())\n'


def _run(env_overrides: dict) -> subprocess.CompletedProcess:
    env = {**os.environ, **env_overrides}
    return subprocess.run([sys.executable, '-c', _CODE], capture_output=True, text=True, env=env, check=False)


def test_real_login_resolves_via_kernel_verified_identity():
    result = _run({})
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == getpass.getuser()


def test_spoofed_human_identity_is_rejected():
    result = _run({'USER': 'not-a-real-login-and-not-xx-prefixed'})
    assert result.returncode != 0
    assert 'Failed to get OS user name' in result.stderr


def test_functional_account_shaped_spoof_is_rejected():
    """A functional-account-shaped name (the `xx-` prefix) gets no special treatment -- it must
    match the real kernel identity, exactly like any other spoofed name."""
    result = _run({'USER': 'xx-some-service', 'LOGNAME': 'xx-some-service'})
    assert result.returncode != 0
    assert 'Failed to get OS user name' in result.stderr
