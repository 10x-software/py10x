from pathlib import Path

import rio
from core_10x.rc import RC, RC_TRUE
from core_10x.trait import Trait
from core_10x.traitable import Traitable
from matplotlib import colors, font_manager

class StyleSheet(Traitable):
    sheet: dict
    text_style: rio.TextStyle

    def sheet_set(self, trait: Trait, value: dict) -> RC:

        #{'color': 'lightgreen', 'background-color': 'white', 'font-family': 'Helvetica', 'font-style': 'normal', 'font-weight': 'normal', 'border-width': '2px', 'border-style': '', 'border-color': 'blue'}
        style = dict(value)
        kw = {}
        if bg_color:=style.pop('color',None):
            kw['fill'] = self.color_from_string(bg_color)

        if font:=style.pop('font-family',None):
            kw['font'] = self.font_from_family(font)

        if font_style:=style.pop('font-style',None):
            if font_style!='normal':
                kw[font_style]=True

        if font_weight:=style.pop('font-weight',None):
            kw['font_weight'] = font_weight

        if kw:
            self.text_style = rio.TextStyle(**kw)

        return self.rc(style)

    @staticmethod
    def rc(ss) -> RC:
        rc = RC(True)
        for style,value in ss.items():
            rc.add_error(f"Unsupported style: {style}: {value}")
        return rc
    
    @staticmethod
    def color_from_string(color):
        return rio.Color.from_rgb(*colors.to_rgba(color))

    @staticmethod
    def font_from_family(family):
        return rio.Font(
            regular=Path(
                font_manager.findfont(
                    font_manager.FontProperties(family=family, weight="normal", style="normal")
                )
            ),
            bold=Path(
                font_manager.findfont(
                    font_manager.FontProperties(family=family, weight="bold", style="normal")
                )
            ),
            italic=Path(
                font_manager.findfont(
                    font_manager.FontProperties(family=family, weight="normal", style="italic")
                )
            ),
            bold_italic=Path(
                font_manager.findfont(
                    font_manager.FontProperties(family=family, weight="bold", style="italic")
                )
            ),
        )

