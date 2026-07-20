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

import pytest

from core_10x.concrete_traits import nucleus_trait
from core_10x.exec_control import CACHE_ONLY
from core_10x.nucleus import Nucleus
from core_10x.package_refactoring import PackageRefactoring
from core_10x.trait_definition import T
from core_10x.traitable import NamedTraitable, Traitable
from core_10x.traitable_id import ID

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


# ---------------------------------------------------------------------------
# NamedTraitable (+ multi-part ID) as non-embedded ref target
# ---------------------------------------------------------------------------
# C++ uses Traitable.from_id(id); NamedTraitable positional first arg is name only.


class NamedCal(NamedTraitable, keep_history=False):
    adjusted_for: str = T(T.ID, default='')


class NamedCcy(NamedTraitable, keep_history=False):
    bank_calendar: NamedCal = T()


def test_named_traitable_name_convenience_and_from_id():
    """NamedTraitable('name') convenience; by-id via from_id / _id= keyword."""
    with CACHE_ONLY():
        cal = NamedCal(name='FD', adjusted_for='', _update=True)
        assert cal.id_value() == 'FD|'
        assert cal.name == 'FD'

        by_name = NamedCal('FD')
        assert by_name.id_value() == 'FD|'
        assert by_name.name == 'FD'

        by_from_id = NamedCal.from_id(ID('FD|'))
        assert by_from_id.id_value() == 'FD|'
        assert by_from_id.name == 'FD'

        by_kw = NamedCal(_id=ID('FD|'))
        assert by_kw.id_value() == 'FD|'
        assert by_kw.name == 'FD'


def test_traitable_init_rejects_positional_id():
    """Traitable.__init__ is keyword-only for construction control args."""
    with CACHE_ONLY():
        RefBase(name='pos_id_probe', _update=True)
        with pytest.raises(TypeError):
            RefBase(ID('pos_id_probe'))  # intentional positional — must raise
        ok = RefBase.from_id(ID('pos_id_probe'))
        assert ok.id_value() == 'pos_id_probe'


def test_named_traitable_ref_deserialize_composite_id():
    """Non-embedded ref to multi-ID NamedTraitable deserializes (dict + packed)."""
    with CACHE_ONLY():
        cal = NamedCal(name='FD', adjusted_for='', _update=True)
        ccy = NamedCcy(name='USD', bank_calendar=cal, _update=True)
        trait = NamedCcy.s_dir['bank_calendar']

        # Nucleus dict wire (legacy store form)
        dict_wire = _nucleus_ser(trait, cal)
        assert dict_wire == {Nucleus.ID_TAG(): 'FD|'}
        back_dict = trait.deserialize(dict_wire)
        assert back_dict.id_value() == 'FD|'
        assert back_dict.name == 'FD'

        # Packed string wire
        ser, back = _roundtrip_packed(trait, cal)
        assert ser == 'FD|'
        assert back.id_value() == 'FD|'
        assert back.name == 'FD'

        # Full holder reload path: deserialize bank_calendar from saved object
        saved = ccy.serialize_object()
        assert saved['bank_calendar'] in ('FD|', {Nucleus.ID_TAG(): 'FD|'})
        reloaded = NamedCcy.deserialize(saved)
        assert reloaded.bank_calendar.id_value() == 'FD|'
        assert reloaded.bank_calendar.name == 'FD'
