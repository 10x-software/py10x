"""Unit tests for `dev_10x.constraints` environment inspection."""
from __future__ import annotations

import json

from dev_10x import constraints as c


def test_check_uses_target_venv_python(monkeypatch, tmp_path):
    venv_python = tmp_path / '.venv' / 'bin' / 'python'
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text('', encoding='utf-8')
    constraints = tmp_path / 'constraints.txt'
    constraints.write_text('requests==2.34.2\n', encoding='utf-8')
    calls = []

    def fake_check_output(args, **kwargs):
        calls.append(args)
        return json.dumps([
            {'name': 'requests', 'version': '2.34.2'},
            {'name': 'py10x-core', 'version': '0.2.3'},
        ])

    monkeypatch.setattr(c, 'PROJECT_ROOT', tmp_path)
    monkeypatch.setattr(c, 'CONSTRAINTS', constraints)
    monkeypatch.setattr(c.subprocess, 'check_output', fake_check_output)

    assert c.check() == 0
    assert calls == [[
        'uv', 'pip', 'list', '--python', str(venv_python), '--format', 'json',
    ]]
