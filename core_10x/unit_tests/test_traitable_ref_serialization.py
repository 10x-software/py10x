"""Traitable reference serialization: nucleus dict wire + traitable_trait string pack.

Not covered: ``T.EMBEDDED`` (full / nx payload dicts).

**Layer 1 — ``nucleus_trait.serialize``** (dict id / nx form; catch format drift)::

- Exact type: ``{_id: str}``
- Subclass: ``{_type: '_nx', _cls: class_id, _obj: {_id: str}}``
- ``custom_collection``: id dict / ``_obj`` also has ``_coll``

**Layer 2 — ``traitable_trait.serialize``** (string pack of that dict)::

- Exact: ``id`` or ``id^collection``
- Subclass: ``class_id~id`` or ``class_id~id^collection``
- Id percent-encodes ``%``, ``~``, ``^`` as ``%xx``
"""

from __future__ import annotations

from core_10x.concrete_traits import nucleus_trait
from core_10x.exec_control import CACHE_ONLY
from core_10x.nucleus import Nucleus
from core_10x.package_refactoring import PackageRefactoring
from core_10x.trait_definition import T
from core_10x.traitable import Traitable

# ---------------------------------------------------------------------------
# Default collection (no custom_collection)
# ---------------------------------------------------------------------------


class RefBase(Traitable, keep_history=False):
    name: str = T(T.ID)


class RefSub(RefBase, keep_history=False):
    x: int = T()


class Holder(Traitable, keep_history=False):
    name: str = T(T.ID)
    peer: RefBase = T()  # non-embedded Traitable ref


# ---------------------------------------------------------------------------
# custom_collection
# ---------------------------------------------------------------------------


class CRefBase(Traitable, custom_collection=True, keep_history=False):
    name: str = T(T.ID)


class CRefSub(CRefBase, keep_history=False):
    x: int = T()


class CHolder(Traitable, custom_collection=True, keep_history=False):
    name: str = T(T.ID)
    peer: CRefBase = T()


def _nucleus_ser(trait, value):
    """Dict wire from ``nucleus_trait`` (bypass string pack)."""
    return nucleus_trait.serialize(trait, value)


def _packed_ser(trait, value):
    """String (or dict fallback) from ``traitable_trait``."""
    return trait.serialize_value(value, replace_xnone=True)


def _roundtrip_packed(trait, value):
    ser = _packed_ser(trait, value)
    back = trait.deserialize(ser)
    return ser, back


# --- nucleus_trait dict form -------------------------------------------------


def test_nucleus_exact_class_serializes_id_dict():
    """Exact declared class → id-only dict; ``_id`` is str."""
    with CACHE_ONLY():
        trait = Holder.s_dir['peer']
        base = RefBase(name='exact_base')
        assert type(base) is RefBase is trait.data_type

        ser = _nucleus_ser(trait, base)
        assert ser == {Nucleus.ID_TAG(): 'exact_base'}
        assert isinstance(ser[Nucleus.ID_TAG()], str)
        assert Nucleus.CLASS_TAG() not in ser
        assert Nucleus.COLLECTION_TAG() not in ser


def test_nucleus_subclass_serializes_nx_record_with_cls():
    """Subclass → nx wrapper with ``_cls`` + id ``_obj``."""
    with CACHE_ONLY():
        trait = Holder.s_dir['peer']
        sub = RefSub(name='sub_inst')
        sub.x = 1
        assert type(sub) is not trait.data_type

        ser = _nucleus_ser(trait, sub)
        assert ser == {
            Nucleus.TYPE_TAG(): Nucleus.NX_RECORD_TAG(),
            Nucleus.CLASS_TAG(): PackageRefactoring.find_class_id(RefSub),
            Nucleus.OBJECT_TAG(): {Nucleus.ID_TAG(): 'sub_inst'},
        }
        assert isinstance(ser[Nucleus.OBJECT_TAG()][Nucleus.ID_TAG()], str)
        assert Nucleus.COLLECTION_TAG() not in ser[Nucleus.OBJECT_TAG()]


def test_nucleus_custom_collection_exact_includes_coll():
    """Exact type + custom_collection → ``{_id, _coll}``."""
    with CACHE_ONLY():
        trait = CHolder.s_dir['peer']
        coll = 'my_custom_coll'
        base = CRefBase(name='c_exact', _collection_name=coll)

        ser = _nucleus_ser(trait, base)
        assert ser == {
            Nucleus.ID_TAG(): 'c_exact',
            Nucleus.COLLECTION_TAG(): coll,
        }


def test_nucleus_custom_collection_subclass_nx_obj_includes_coll():
    """Subclass + custom_collection → nx; ``_obj`` has ``_id`` and ``_coll``."""
    with CACHE_ONLY():
        trait = CHolder.s_dir['peer']
        coll = 'other_coll'
        sub = CRefSub(name='c_sub', _collection_name=coll)
        sub.x = 2

        ser = _nucleus_ser(trait, sub)
        assert ser == {
            Nucleus.TYPE_TAG(): Nucleus.NX_RECORD_TAG(),
            Nucleus.CLASS_TAG(): PackageRefactoring.find_class_id(CRefSub),
            Nucleus.OBJECT_TAG(): {
                Nucleus.ID_TAG(): 'c_sub',
                Nucleus.COLLECTION_TAG(): coll,
            },
        }


# --- traitable_trait string pack ---------------------------------------------


def test_pack_exact_class_to_id_string():
    """Exact type → ``id`` string (pack of nucleus id dict)."""
    with CACHE_ONLY():
        trait = Holder.s_dir['peer']
        base = RefBase(name='exact_base')
        assert _nucleus_ser(trait, base) == {Nucleus.ID_TAG(): 'exact_base'}
        ser, back = _roundtrip_packed(trait, base)
        assert ser == 'exact_base'
        assert type(back) is RefBase
        assert back.id_value() == 'exact_base'


def test_pack_subclass_to_class_tilde_id():
    """Subclass → ``class_id~id``."""
    with CACHE_ONLY():
        trait = Holder.s_dir['peer']
        sub = RefSub(name='sub_inst')
        sub.x = 1
        cls_id = PackageRefactoring.find_class_id(RefSub)
        assert _nucleus_ser(trait, sub)[Nucleus.CLASS_TAG()] == cls_id
        ser, back = _roundtrip_packed(trait, sub)
        assert ser == f'{cls_id}~sub_inst'
        assert type(back) is RefSub
        assert back.id_value() == 'sub_inst'


def test_pack_custom_collection_exact_id_caret_collection():
    """Exact + custom_collection → ``id^collection``."""
    with CACHE_ONLY():
        trait = CHolder.s_dir['peer']
        coll = 'my_custom_coll'
        base = CRefBase(name='c_exact', _collection_name=coll)
        ser, back = _roundtrip_packed(trait, base)
        assert ser == f'c_exact^{coll}'
        assert back.id().collection_name == coll


def test_pack_custom_collection_subclass_class_tilde_id_caret_collection():
    """Subclass + custom_collection → ``class_id~id^collection``."""
    with CACHE_ONLY():
        trait = CHolder.s_dir['peer']
        coll = 'other_coll'
        sub = CRefSub(name='c_sub', _collection_name=coll)
        sub.x = 2
        cls_id = PackageRefactoring.find_class_id(CRefSub)
        ser, back = _roundtrip_packed(trait, sub)
        assert ser == f'{cls_id}~c_sub^{coll}'
        assert type(back) is CRefSub
        assert back.id().collection_name == coll


def test_pack_id_with_separators_is_percent_encoded():
    """Id ``~``, ``^``, and ``%`` are packed as ``%xx`` and round-trip."""
    with CACHE_ONLY():
        trait = Holder.s_dir['peer']
        for raw_id, encoded in (
            ('has~tilde', 'has%7Etilde'),
            ('has^caret', 'has%5Ecaret'),
            ('100%', '100%25'),
            ('a%~^b', 'a%25%7E%5Eb'),
        ):
            base = RefBase(name=raw_id)
            ser, back = _roundtrip_packed(trait, base)
            assert ser == encoded
            assert back.id_value() == raw_id


def test_pack_separator_in_collection_ok():
    """Collection may contain ``~``; unpack uses rsplit on ``^``."""
    with CACHE_ONLY():
        trait = CHolder.s_dir['peer']
        coll = 'my~coll'
        base = CRefBase(name='cid', _collection_name=coll)
        ser, back = _roundtrip_packed(trait, base)
        assert ser == f'cid^{coll}'
        assert back.id().collection_name == coll


def test_legacy_dict_wire_still_deserializes():
    """Dict id / nx forms remain accepted on deserialize."""
    with CACHE_ONLY():
        trait = Holder.s_dir['peer']
        RefBase(name='legacy')
        back = trait.deserialize({'_id': 'legacy'})
        assert back.id_value() == 'legacy'
        cls_id = PackageRefactoring.find_class_id(RefSub)
        RefSub(name='legacy_sub')
        back2 = trait.deserialize({'_type': '_nx', '_cls': cls_id, '_obj': {'_id': 'legacy_sub'}})
        assert type(back2) is RefSub
        assert back2.id_value() == 'legacy_sub'
