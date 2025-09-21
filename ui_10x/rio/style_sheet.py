from core_10x.rc import RC
from core_10x.trait import Trait
from core_10x.traitable import Traitable
from matplotlib import colors, font_manager

import rio


class StyleSheet(Traitable):
    sheet: dict
    text_style: rio.TextStyle

    def sheet_set(self, trait: Trait, value: dict) -> RC:

        #{'color': 'lightgreen', 'background-color': 'white', 'font-family': 'Helvetica', 'font-style': 'normal', 'font-weight': 'normal', 'border-width': '2px', 'border-style': '', 'border-color': 'blue'}
        style = dict(value)
        kw = {}
        if bg_color:=style.pop('color',None):
            kw['fill'] = rio.Color.from_hex(colors.to_hex(bg_color))

        if font:=style.pop('font-family',None):
            kw['font'] = rio.Font.from_google_fonts(font)

        if font_style:=style.pop('font-style',None):
            if font_style!='normal':
                kw[font_style]=True

        if font_weight:=style.pop('font-weight',None):
            kw['font_weight'] = font_weight

        if kw:
            self.text_style = rio.TextStyle(**kw)

        return self.rc(style)

    def sheet_get(self):
        style = {}
        ts = self.text_style
        if ts:
            style['font-style'] = 'italic' if ts.italic else 'normal'
            style['font-weight'] = ts.font_weight or "normal"
            style['font-family'] = font_manager.get_font([ts.font.regular]).family_name
            style['color'] = f'#{ts.fill.hex}'
        return style

    @staticmethod
    def rc(ss) -> RC:
        rc = RC(True)
        for style,value in ss.items():
            rc.add_error(f"Unsupported style: {style}: {value}")
        return rc



