"""`OsUser.me.name()` (`cxx10x/core_10x/os_user.cpp`) caches for the process lifetime, so
each scenario runs in its own subprocess. Unix: `getpwuid(geteuid())`. Windows:
`GetUserNameA`. `$USER`/`$LOGNAME` are never read. See docs/VAULT_SECURITY_DESIGN.md §3.2.
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


def test_user_env_var_has_no_effect_on_resolved_identity():
    result = _run({'USER': 'not-a-real-login-and-not-xx-prefixed'})
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == getpass.getuser()


def test_functional_account_shaped_user_env_var_has_no_effect_either():
    """A functional-account-shaped name (the `xx-` prefix) gets no special treatment -- it's
    ignored exactly like any other `$USER`/`$LOGNAME` value."""
    result = _run({'USER': 'xx-some-service', 'LOGNAME': 'xx-some-service'})
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == getpass.getuser()
