from core_10x.traitable import T, Traitable, Ui
from core_10x.ts_union import TsUnion

COLORS = ('black', 'white', 'green', 'lightgreen', 'red', 'blue', 'grey')

class StyleSheet(Traitable):
    foreground: str     = T('black',        ui_hint = Ui(widget_type = Ui.WIDGET_TYPE.CHOICE))
    background: str     = T('white',        ui_hint = Ui(widget_type = Ui.WIDGET_TYPE.CHOICE, flags = Ui.SEPARATOR))

    font: str           = T('Helvetica',    ui_hint = Ui(widget_type = Ui.WIDGET_TYPE.CHOICE))
    font_style: bool    = T(False,          ui_hint = Ui('italic', right_label = True))
    font_weight: bool   = T(False,          ui_hint = Ui('bold', flags = Ui.SEPARATOR, right_label = True))

    border_style: bool  = T(False)
    border_color: str   = T('blue',         ui_hint = Ui(widget_type = Ui.WIDGET_TYPE.CHOICE))
    border_width: int   = T(2,              ui_hint = Ui(flags = Ui.SEPARATOR))

    show_me: str        = T('This is how it will look...',  ui_hint = Ui('WYSIWYG', min_width = 50))

    def foreground_choices(self, t):    return COLORS
    def background_choices(self, t):    return COLORS
    def border_color_choices(self, t):  return COLORS
    def font_choices(self, t):          return ('Times New Roman', 'Helvetica', 'Courier New')

    def show_me_style_sheet(self) -> dict:
        ss = {
            Ui.FG_COLOR:        self.foreground,
            Ui.BG_COLOR:        self.background,
            Ui.FONT:            self.font,
            Ui.FONT_STYLE:      'italic'   if self.font_style    else 'normal',
            Ui.FONT_WEIGHT:     'bold'     if self.font_weight   else 'normal',
            Ui.BORDER_WIDTH:    f'{self.border_width}px',
            Ui.BORDER_STYLE:    'solid'    if self.border_style  else '',
            Ui.BORDER_COLOR:    self.border_color,
        }
        print(ss)
        return ss

if __name__ == '__main__':
    from ui_10x.traitable_editor import TraitableEditor

    with TsUnion():
        sheet = StyleSheet()
        e = TraitableEditor(sheet, _confirm = True)
        e.dialog().exec()


