from core_10x.traitable import Traitable, RT, Ui
from ui_10x.examples.constants import COLOR, FONT

class StyleSheet(Traitable):
    foreground: COLOR   = RT(COLOR.LIGHTGREEN)
    background: COLOR   = RT(COLOR.BLACK,   ui_hint = Ui(flags = Ui.SEPARATOR))

    font: FONT          = RT(FONT.HELVETICA)
    italic: bool        = RT(True,          ui_hint = Ui('italic',  right_label = True))
    bold: bool          = RT(False,         ui_hint = Ui('bold',    right_label = True, flags = Ui.SEPARATOR))

    border: bool        = RT(True)
    border_color: COLOR = RT(COLOR.BLUE)
    border_width: int   = RT(2,             ui_hint = Ui(flags = Ui.SEPARATOR))

    show_me: str        = RT('This is how it will look...',  ui_hint = Ui('WYSIWYG', min_width = 50))

    def show_me_style_sheet(self) -> dict:
        return {
            Ui.FG_COLOR:        self.foreground.value,
            Ui.BG_COLOR:        self.background.value,
            Ui.FONT:            self.font.value,
            Ui.FONT_STYLE:      'italic'   if self.italic   else 'normal',
            Ui.FONT_WEIGHT:     'bold'     if self.bold     else 'normal',
            Ui.BORDER_WIDTH:    f'{self.border_width}px',
            Ui.BORDER_STYLE:    'solid'    if self.border   else '',
            Ui.BORDER_COLOR:    self.border_color.value,
        }

if __name__ == '__main__':
    from ui_10x.traitable_editor import TraitableEditor

    sheet = StyleSheet()
    e = TraitableEditor(sheet, _confirm = True)
    e.popup()

