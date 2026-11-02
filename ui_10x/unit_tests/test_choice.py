"""Initial MultiChoice selection, without a widget."""

from ui_10x.choice import MultiChoice

_CHOICES = {'red': 'blue', 'blue': 'green'}


def test_label_wins_when_it_collides_with_another_choices_value():
    # 'blue' is the label of green and the value of red. The label must win.
    mc = MultiChoice('blue', choices=_CHOICES)
    assert mc.values_selected == ['green']


def test_value_that_is_not_a_label_stays_selected():
    mc = MultiChoice('green', choices=_CHOICES)
    assert mc.values_selected == ['green']


def test_label_that_is_not_a_value_maps_to_its_value():
    mc = MultiChoice('red', choices=_CHOICES)
    assert mc.values_selected == ['blue']
