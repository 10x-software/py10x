import inspect
import copy

from core_10x.trait import Ui, T
from core_10x.traitable import Traitable
from core_10x.global_cache import cache


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

    @staticmethod
    def slice(traitable_class, _header_data: dict = None, **named_ui_hints) -> 'TraitableView':
        assert inspect.isclass(traitable_class) and issubclass(traitable_class, Traitable), f'{traitable_class} is not a Traitable'

        trait_dir = traitable_class.s_dir
        ui_hints = { name: hint_modification.apply(trait.ui_hint) for name, hint_modification in named_ui_hints.items() if (trait := trait_dir.get(name))}
        return TraitableView(traitable_class, ui_hints, _header_data)

    @staticmethod
    def modify(traitable_class, _header_data: dict = None, _skip_reserved = True, **named_ui_hints) -> 'TraitableView':
        assert inspect.isclass(traitable_class) and issubclass(traitable_class, Traitable), f'{traitable_class} is not a Traitable'

        if _skip_reserved:
            ui_hints = {trait_name: trait.ui_hint for trait_name, trait in traitable_class.s_dir.items() if not trait.flags_on(T.RESERVED)}
        else:
            ui_hints = {trait_name: trait.ui_hint for trait_name, trait in traitable_class.s_dir.items()}

        for name, hint_modification in named_ui_hints.items():
            hint = ui_hints.get(name)
            if hint is not None:
                ui_hints[name] = hint_modification.apply(hint)

        return TraitableView(traitable_class, ui_hints, _header_data)

    @staticmethod
    @cache
    def default(traitable_class, read_only = False) -> 'TraitableView':
        return TraitableView.modify(traitable_class).make_read_only(read_only, clone = True)

    def make_read_only(self, flag: bool, clone = False) -> 'TraitableView':
        view = self if not clone else copy.deepcopy(self)

        to_set = Ui.READ_ONLY if flag else 0x0
        to_reset = 0x0 if flag else Ui.READ_ONLY
        for name, ui_hint in view.ui_hints.items():
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
                if not hint:  #-- ignore an unknown or unused trait
                    continue
                if not label:  #-- no label overwrite
                    label = hint.label
                header[subtree_name] = label

            elif isinstance(subtree, dict):     #-- must be a real subtree
                header[subtree_name] = TraitableView._process_tree(ui_hints, subtree)

            else:
                continue  #-- ignore anything else

        return header

    @staticmethod
    def create_header(ui_hints: dict, header_data: dict) -> dict:
        if not header_data:
            return {trait_name: ui.label for trait_name, ui in ui_hints.items()}

        return TraitableView._process_tree(ui_hints, header_data)
