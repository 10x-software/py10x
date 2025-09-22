from __future__ import annotations

import copy
import inspect

from core_10x.global_cache import cache
from core_10x.trait import T, Trait
from core_10x.traitable import Traitable
from core_10x.ui_hint import Ui, UiMod


class TraitableView:
    """
    To create an instance of EntityView you need to pass the following args:
    1) entity_or_class: a subclass of Entity or an instance of it
    2) _header_data: a dictionary with each item as follows:
        either
            <trait-name>:   <label>     (if label is empty, the trait's label will be used)
        or
            <group-label>:  <header>    (_header like dict)
    3) named_traits_to_use: (kwargs) with each item as follows:
            <trait-name>:   Ui(...)

        Such named_traits specify either traits to use (slice) or the ones to modify (modify)
    """

    @classmethod
    def _check(cls, hint_mod, trait_name: str) -> bool:
        assert isinstance(hint_mod, UiMod), f'{trait_name} = {hint_mod} - UiMod is expected'
        return True

    @classmethod
    def suitable_record(cls, trait: Trait = None, trait_dir: dict = None, trait_name: str = None, _skip_reserved: bool = True) -> Trait | None:
        if not trait:
            assert trait_dir and trait_name, 'trait is None, so both trait_dir and trait_name must be provided'
            trait = trait_dir.get(trait_name)
            if not trait:
                return None

        flags = T.HIDDEN | T.RESERVED if _skip_reserved else T.HIDDEN
        return None if trait.flags_on(flags) or trait.getter_params else trait

    @classmethod
    def slice(cls, traitable_class, _header_data: dict = None, **named_ui_hint_changes) -> TraitableView:
        assert inspect.isclass(traitable_class) and issubclass(traitable_class, Traitable), f'{traitable_class} is not a Traitable'

        trait_dir = traitable_class.s_dir
        trait: Trait
        ui_hints = {
            name: hint_change.apply(trait.ui_hint) if cls._check(hint_change, trait.name) else None
            for name, hint_change in named_ui_hint_changes.items()
            if (trait := cls.suitable_record(trait_dir=trait_dir, trait_name=name))
        }
        return TraitableView(traitable_class, ui_hints, _header_data)

    @classmethod
    def modify(
        cls, traitable_class: type[Traitable], _header_data: dict = None, _skip_reserved: bool = True, **named_ui_hint_changes
    ) -> TraitableView:
        assert inspect.isclass(traitable_class) and issubclass(traitable_class, Traitable), f'{traitable_class} is not a Traitable'

        ui_hints = {
            trait_name: trait.ui_hint
            for trait_name, trait in traitable_class.s_dir.items()
            if TraitableView.suitable_record(trait=trait, _skip_reserved=_skip_reserved)
        }

        for name, hint_change in named_ui_hint_changes.items():
            cls._check(hint_change, name)
            hint = ui_hints.get(name)
            if hint is not None:
                ui_hints[name] = hint_change.apply(hint)

        return TraitableView(traitable_class, ui_hints, _header_data)

    @staticmethod
    @cache
    def default(traitable_class: type[Traitable], read_only: bool = False) -> TraitableView:
        return TraitableView.modify(traitable_class).make_read_only(read_only, clone=True)

    def make_read_only(self, flag: bool, clone=False) -> TraitableView:
        view = self if not clone else copy.deepcopy(self)

        to_set = Ui.READ_ONLY if flag else 0x0
        to_reset = 0x0 if flag else Ui.READ_ONLY
        for ui_hint in view.ui_hints.values():
            ui_hint.set_reset_flags(to_set, to_reset)
        return view

    def __init__(self, traitable_class, ui_hints: dict, header_data: dict):
        self.cls = traitable_class
        self.ui_hints = ui_hints
        self.header = self.create_header(ui_hints, header_data)

    def all_hints(self) -> dict:
        return self.ui_hints

    def ui_hint(self, trait_name: str) -> Ui:
        return self.ui_hints[trait_name]

    @staticmethod
    def _process_tree(ui_hints: dict, tree: dict) -> dict:
        header = {}
        for subtree_name, subtree in tree.items():
            if isinstance(subtree, str):  # -- must be a trait name
                label = subtree
                hint = ui_hints.get(subtree_name)
                if not hint:  # -- ignore an unknown or unused trait
                    continue
                if not label:  # -- no label overwrite
                    label = hint.label
                header[subtree_name] = label

            elif isinstance(subtree, dict):  # -- must be a real subtree
                header[subtree_name] = TraitableView._process_tree(ui_hints, subtree)

            else:
                continue  # -- ignore anything else

        return header

    @staticmethod
    def create_header(ui_hints: dict, header_data: dict) -> dict:
        if not header_data:
            return {trait_name: ui.label for trait_name, ui in ui_hints.items()}

        return TraitableView._process_tree(ui_hints, header_data)
