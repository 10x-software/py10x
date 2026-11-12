"""Unit tests for core_10x/exec_control.py."""

from __future__ import annotations

from core_10x import exec_control
from core_10x.exec_control import ExecControl
from core_10x.package_refactoring import PackageRefactoring


class TestExecControl:
    def test_all_caps_names_are_the_class_methods(self):
        names = [name for name, member in vars(ExecControl).items() if isinstance(member, staticmethod)]
        assert names
        for name in names:
            assert getattr(exec_control, name.upper()) is getattr(ExecControl, name)

    def test_class_id_round_trip(self):
        """Why ExecControl is a class: the family can be referenced by one class id."""
        assert PackageRefactoring.find_class(PackageRefactoring.find_class_id(ExecControl)) is ExecControl
