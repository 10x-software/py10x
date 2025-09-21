import matplotlib.colors
from ui_10x.rio.style_sheet import StyleSheet

import rio


def test_ss_to_ts():
    sheet = {'color': 'lightgreen', 'background-color': 'white', 'font-family': 'Helvetica', 'font-style': 'italic', 'font-weight': 'bold', 'border-width': '2px', 'border-style': '', 'border-color': 'blue'}
    ss = StyleSheet()
    rc = ss.set_values(sheet=sheet)
    assert not rc
    assert 'background-color' in rc.error()
    assert 'border-color' in rc.error()
    assert 'border-style' in rc.error()
    assert 'border-style' in rc.error()
    assert 'border-width' in rc.error()
    ts = ss.text_style
    assert ts.italic
    assert ts.font_weight == "bold"
    assert 'Helvetica' in ts.font.regular.as_uri()
    assert matplotlib.colors.same_color(f'#{ts.fill.hex}','lightgreen')


def test_ts_to_ss():
    ss = StyleSheet()
    rc = ss.set_values(text_style=rio.TextStyle(font=rio.Font.ROBOTO_MONO,fill=rio.Color.from_hex('#c5f7c5')))
    assert rc
    assert ss.sheet == {'color': '#c5f7c5', 'font-family': 'Roboto Mono', 'font-style': 'normal', 'font-weight': 'normal'}
