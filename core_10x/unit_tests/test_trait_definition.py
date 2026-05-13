import pytest

from core_10x.trait_definition import T, RT, M, TraitDefinition, TraitModification
from core_10x.xnone import XNone, XNoneType


# ----------------------------------------------------------------------------
#   T() / TraitDefinition construction
# ----------------------------------------------------------------------------

def test_t_returns_trait_definition():
    td = T()
    assert isinstance(td, TraitDefinition)


def test_t_default_value_is_xnone():
    td = T()
    assert td.default is XNone


def test_t_default_data_type_is_xnonetype():
    td = T()
    assert td.data_type is XNoneType


def test_t_name_is_none_on_construction():
    assert T().name is None


def test_t_with_int_default():
    td = T(42)
    assert td.default == 42


def test_t_with_string_default():
    td = T('hello')
    assert td.default == 'hello'


def test_t_with_none_default():
    td = T(None)
    assert td.default is None


def test_t_with_explicit_data_type():
    td = T(data_type=int)
    assert td.data_type is int


def test_t_with_explicit_fmt():
    td = T(fmt='.2f')
    assert td.fmt == '.2f'


def test_t_extra_kwargs_stored_in_params():
    td = T(custom_key='val')
    assert td.params.get('custom_key') == 'val'


def test_t_flags_default_is_zero():
    td = T()
    assert td.flags.value() == 0


# ----------------------------------------------------------------------------
#   T with flag argument
# ----------------------------------------------------------------------------

def test_t_with_id_flag_sets_id_bit():
    id_td = T(T.ID)
    plain_td = T()
    id_val = T.ID.value()
    assert id_td.flags.value() & id_val == id_val
    assert plain_td.flags.value() & id_val == 0


def test_t_with_id_flag_leaves_default_as_xnone():
    td = T(T.ID)
    assert td.default is XNone


def test_t_id_with_explicit_default():
    td = T(T.ID, default=1)
    assert td.default == 1
    assert td.flags.value() & T.ID.value() != 0


# ----------------------------------------------------------------------------
#   RT()
# ----------------------------------------------------------------------------

def test_rt_returns_trait_definition():
    assert isinstance(RT(), TraitDefinition)


def test_rt_sets_runtime_flag():
    td = RT()
    runtime_val = T.RUNTIME.value()
    assert td.flags.value() & runtime_val == runtime_val


def test_rt_plain_t_does_not_have_runtime_flag():
    plain = T()
    runtime_val = T.RUNTIME.value()
    assert plain.flags.value() & runtime_val == 0


def test_rt_with_default_value():
    td = RT(99)
    assert td.default == 99
    assert td.flags.value() & T.RUNTIME.value() != 0


# ----------------------------------------------------------------------------
#   __floordiv__ — UI tip comment
# ----------------------------------------------------------------------------

def test_floordiv_sets_ui_hint_tip():
    td = T() // 'my tooltip'
    assert td.ui_hint.tip == 'my tooltip'


def test_floordiv_returns_same_instance():
    td = T()
    result = td // 'tip'
    assert result is td


def test_floordiv_non_string_raises_assertion():
    with pytest.raises(AssertionError):
        T() // 123


def test_floordiv_replaces_existing_tip():
    td = T() // 'first'
    td // 'second'
    assert td.ui_hint.tip == 'second'


# ----------------------------------------------------------------------------
#   T static color helpers
# ----------------------------------------------------------------------------

def test_fg_color_with_color():
    assert T.fg_color('red') == 'color: red'


def test_fg_color_empty_string_returns_empty():
    assert T.fg_color('') == ''


def test_bg_color_with_color():
    assert T.bg_color('blue') == 'background-color: blue'


def test_bg_color_empty_returns_empty():
    assert T.bg_color('') == ''


def test_colors_both_provided():
    result = T.colors('blue', 'white')
    assert 'background-color: blue' in result
    assert 'color: white' in result


def test_colors_empty_bg_returns_empty():
    assert T.colors('', 'white') == ''


def test_colors_empty_fg_returns_empty():
    assert T.colors('blue', '') == ''


def test_colors_both_empty_returns_empty():
    assert T.colors('', '') == ''


# ----------------------------------------------------------------------------
#   copy
# ----------------------------------------------------------------------------

def test_trait_definition_copy_is_independent():
    td = T(42)
    td2 = td.copy()
    assert td2 is not td
    assert td2.default == 42


def test_trait_definition_copy_deep_copies_ui_hint():
    td = T() // 'original'
    td2 = td.copy()
    td2 // 'modified'
    assert td.ui_hint.tip == 'original'
    assert td2.ui_hint.tip == 'modified'


# ----------------------------------------------------------------------------
#   M() / TraitModification
# ----------------------------------------------------------------------------

def test_m_returns_trait_modification():
    assert isinstance(M(), TraitModification)


def test_m_apply_returns_copy_not_same_instance():
    original = T(10)
    modified = M().apply(original)
    assert modified is not original


def test_m_apply_preserves_default_when_no_change():
    original = T(10)
    modified = M().apply(original)
    assert modified.default == 10


def test_m_floordiv_applies_tip_via_apply():
    original = T(10)
    m = M() // 'new tip'
    result = m.apply(original)
    assert result.ui_hint.tip == 'new tip'


def test_m_apply_does_not_mutate_original():
    original = T(10) // 'keep me'
    M() // 'other'
    assert original.ui_hint.tip == 'keep me'


# ----------------------------------------------------------------------------
#   T.STICKY alias
# ----------------------------------------------------------------------------

def test_t_sticky_has_same_value_as_offgraph_set():
    from py10x_kernel import BTraitFlags
    assert T.STICKY.value() == BTraitFlags.OFFGRAPH_SET.value()
