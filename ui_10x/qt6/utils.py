from datetime import date
import inspect
import platform

from PyQt6.QtWidgets import QLabel, QWidget, QCalendarWidget, QMessageBox, QGroupBox, QButtonGroup, QRadioButton, QApplication
from PyQt6.QtWidgets import QListWidget, QLineEdit, QTreeWidgetItem, QTreeWidget, QSizePolicy
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QSplitter, QDialog, QScrollArea, QPushButton, QStyle
from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal, QBuffer, QIODevice    #, QByteArray
from PyQt6.QtGui import QColor, QGuiApplication, QPixmap

# from asu.nx.directory import Directory

from core_10x.named_constant import NamedConstant
from core_10x.rc import RC
from core_10x.global_cache import cache, singleton

class UxAsync(QObject):
    SIGNAL          = pyqtSignal()
    s_instances     = {}

    @classmethod
    def _check_thread(cls, bound_method):
        if QThread.currentThread() != QGuiApplication.instance().thread():
            raise RuntimeError(f'You must have called UxAsync.init({bound_method.__name__}) in the UI thread')

    @classmethod
    def init(cls, bound_method):
        instance = cls.s_instances.get(bound_method)
        if not instance:
            cls._check_thread(bound_method)
            instance = cls()
            cls.s_instances[bound_method] = instance

            instance.SIGNAL.connect(bound_method, type = Qt.ConnectionType.QueuedConnection)

        return instance

    @classmethod
    def call(cls, bound_method):
        instance = cls.init(bound_method)
        instance.SIGNAL.emit()

class UxRadioBox(QGroupBox):
    def __init__(self, named_constant_class, title = '', horizontal = False, default_value: NamedConstant = None):
        assert inspect.isclass(named_constant_class) and issubclass(named_constant_class, NamedConstant), 'subclass of NamedConstant is expected'

        self.nm_class = named_constant_class
        self.values = values = list(named_constant_class.s_dir.values())

        if default_value is None:
            default = 0
        else:
            assert isinstance(default_value, named_constant_class), f'{named_constant_class} - unknown default_values = {default_value}'
            for i, c_def in enumerate(values):
                if c_def is default_value:
                    default = i
                    break
            else:
                assert False, f'{default_value} is not found'

        if title:
            super().__init__(title)
        else:
            super().__init__()


        lay = QHBoxLayout() if horizontal else QVBoxLayout()
        self.setLayout(lay)

        self.group = group = QButtonGroup()
        for i, c_def in enumerate(named_constant_class.s_dir.values()):
            rb = QRadioButton(c_def.label)
            lay.addWidget(rb)
            group.addButton(rb, id = i)
        group.button(default).setChecked(True)

    def choice(self):
        i = self.group.checkedId()
        return self.values[i]

def uxSeparator(horizontal = True) -> QLabel:
    direction = QFrame.Shape.HLine if horizontal else QFrame.Shape.VLine
    sep = QLabel()
    sep.setFrameStyle(direction | QFrame.Shadow.Sunken)
    return sep

def uxToClipboard(text: str, **kwargs):
    cp = QGuiApplication.clipboard()
    cp.setText(text)

def uxFromClipboard(**kwargs) -> str:
    cp = QGuiApplication.clipboard()
    return cp.text()

def uxSuccess(text: str, parent = None, title = ''):
    if not title:
        title = 'Success'
    if not parent:
        parent = None
    QMessageBox.information(parent, title, text)

def uxWarning(text: str, parent = None, title = ''):
    if not title:
        title = 'Warning'
    if not parent:
        parent = None
    QMessageBox.warning(parent, title, text)

def uxAnswer(question: str, parent = None, title = '') -> bool:
    if not title:
        title = 'Waiting for your answer...'
    if not parent:
        parent = None
    sb = QMessageBox.question(parent, title, question)
    return True if sb == QMessageBox.StandardButton.Yes else False

def uxMultiChoiceAnswer(named_constant_class, parent = None, title = '', default_value: NamedConstant = None):
    if not title:
        title = 'Pick one of the choices below:'

    if not parent:
        parent = None

    box = UxRadioBox(named_constant_class, default_value = default_value)
    d = UxDialog(box, parent = parent, title = title, cancel = '')
    d.exec()
    return box.choice()

def uxPushButton(label: str, callback = None, style_icon = None, flat = False):
    if style_icon:
        if isinstance(style_icon, str):
            style_icon = getattr(QStyle, 'SP_' + style_icon, None)
            assert style_icon, f"Unknown style_icon = '{style_icon}'"

        assert isinstance(style_icon, int), 'Currently only str or int are supported for style_icon'

        style = QApplication.style()
        icon = style.standardIcon(style_icon)
        button = QPushButton(icon, label)
    else:
        button = QPushButton(label)

    if callback:
        button.clicked.connect(callback)

    if flat:
        button.setFlat(True)

    return button

class UxDialog(QDialog):
    def _createButton(self, ok: bool, button_spec) -> QPushButton:
        if not button_spec:
            return None

        if isinstance(button_spec, str):
            label = button_spec
            icon = ''

        elif isinstance(button_spec, tuple):
            try:
                label, icon = button_spec
            except Exception:
                return None

        else:
            return None

        cb = self.onOk if ok else self.onCancel
        return uxPushButton(label, callback = cb, style_icon = icon)

    def __init__(
            self,
            w: QWidget,
            parent: QWidget     = None,
            title: str          = None,
            ok                  = 'Ok',
            cancel              = 'Cancel',
            accept_callback     = None,
            cancel_callback     = None,
            min_width           = 0,
            min_height          = 0,
            window_flags        = None
    ):
        """
        :param w:               a QWidget to show
        :param parent:          parent widget, if any
        :param title:           dialog title
        :param accept_callback: context.method, where: method( context ) -> RC
        :param ok, cancel:      labels and corresponding roles for Ok and Cancel buttons. No button if empty
        """
        super().__init__( parent )
        if title:
            self.setWindowTitle( title )

        if window_flags is None:
            window_flags = Qt.WindowType.CustomizeWindowHint | Qt.WindowType.Window | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint

        self.setWindowFlags(window_flags)
        self.accept_callback = accept_callback
        self.cancel_callback = cancel_callback if cancel_callback else self.reject

        if ok:
            ok = self._createButton(True, ok)
        if cancel:
            cancel = self._createButton(False, cancel)

        lay = QVBoxLayout()
        self.setLayout(lay)

        lay.addWidget(w)

        self.w_message = QLabel()
        self.w_message.setStyleSheet('color: red;')
        lay.addWidget(self.w_message)

        if ok or cancel:
            lay.addWidget(uxSeparator())

            bar = QHBoxLayout()
            lay.addLayout(bar)

            bar.addWidget(QLabel(), stretch = 1)
            if ok:
                bar.addWidget(ok)
            if cancel:
                bar.addWidget(cancel)

        if min_width > 0:
            self.setMinimumWidth(min_width)
        if min_height > 0:
            self.setMinimumHeight(min_height)

    def onOk(self):
        if self.accept_callback:
            rc = self.accept_callback()
            if not rc:
                self.message(rc.err())
                return

        self.done(1)

    def onCancel(self):
        self.reject()
        self.done(0)

    def message(self, text: str):
        self.w_message.setText(text)

def uxPickDate(title = 'Pick a Date', show_date: date = None, grid = True, default = None):
    cal = QCalendarWidget()
    cal.setGridVisible(bool(grid))
    if show_date:
        cal.setSelectedDate(show_date)
    dlg = UxDialog(cal, title = title)
    rc = dlg.exec()

    return cal.selectedDate().toPyDate() if rc else default

class UxStyleSheet:
    @classmethod
    def dumps(cls, data: dict) -> str:
        return '\n'.join(f'{name}: {value};' for name, value in data.items())

    @classmethod
    def loads(cls, sheet: str) -> dict:
        res = {}
        pairs = sheet.split(';')
        for pair in pairs:
            pair = pair.strip()
            if pair:
                name_value = pair.split(':')
                if len(name_value) == 2:
                    name = name_value[0].strip()
                    value = name_value[1].strip()
                    res[name] = value

        return res

    @classmethod
    def slice(cls, w: QWidget, *attr_names) -> list:
        data = cls.loads(w.styleSheet())
        return [ data.get(name) for name in attr_names ]

    @classmethod
    def update(cls, w: QWidget, sheet_update: str, replace = False):
        if not replace:
            sh = w.styleSheet()
            data = cls.loads(sh)
            update_data = cls.loads(sheet_update)
            data.update(update_data)
            new_sh = cls.dumps(data)
        else:
            new_sh = sheet_update

        w.setStyleSheet(new_sh)

    @classmethod
    def _color(cls, style_sheet: str, attr_name: str):
        data = cls.loads(style_sheet)
        str_color = data.get(attr_name)
        return QColor(str_color) if str_color else None

    @classmethod
    def fg_color(cls, style_sheet: str) -> QColor:
        return cls._color(style_sheet, 'color')

    @classmethod
    def bg_color(cls, style_sheet: str) -> QColor:
        return cls._color(style_sheet, 'background-color')

    @classmethod
    def color(cls, style_sheet: str, background = False) -> QColor:
        return cls.bg_color(style_sheet) if background else cls.fg_color(style_sheet)

s_verticalAlignmentMap = {
    -1:     Qt.AlignmentFlag.AlignTop,
    0:      Qt.AlignmentFlag.AlignVCenter,
    1:      Qt.AlignmentFlag.AlignBottom,
}
s_horizontalAlignmentMap = {
    -1:     Qt.AlignmentFlag.AlignLeft,
    0:      Qt.AlignmentFlag.AlignCenter,
    1:      Qt.AlignmentFlag.AlignRight,
}
def uxTextAlignment(align_value: int, horizontal = True) -> int:
    if horizontal:
        return s_horizontalAlignmentMap.get(align_value, Qt.AlignmentFlag.AlignRight) | Qt.AlignmentFlag.AlignVCenter

    raise NotImplementedError

class UX_SCROLL:
    OFF         = Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    ON          = Qt.ScrollBarPolicy.ScrollBarAlwaysOn
    AS_NEEDED   = Qt.ScrollBarPolicy.ScrollBarAsNeeded

def uxMakeScrollable(w: QWidget, h = UX_SCROLL.AS_NEEDED, v = UX_SCROLL.AS_NEEDED) -> QWidget:
    if h is UX_SCROLL.OFF and v is UX_SCROLL.OFF:
        return w

    sa = QScrollArea()
    sa.setWidget(w)
    sa.setHorizontalScrollBarPolicy(h)
    sa.setVerticalScrollBarPolicy(v)
    return sa

class UxSearchableList(QGroupBox):
    def __init__(
        self,
        text_widget: QLineEdit = None,
        reset_selection = True,
        choices: list   = None,
        select_hook     = None,
        sort            = False,
        case_sensitive  = False,
        title           = ''
    ):
        """
        :param text_widget: if an external text_widget given, it is used, otherwise its own is created on top of the list
        :param reset_selection: if True, text_widget will be reset on new selection
        :param choices: all choices
        :param select_hook: if given, will be called after a new selection is made: select_hook( selected_choice: str )
        :param sort: sort choices if True
        :param case_sensitive: whether to search with case sensitivity
        :param title: an optional title
        """
        super().__init__()
        self.m_sort = sort
        self.m_initialChoices = choices if not sort else sorted( choices )
        self.m_currentChoices = self.m_initialChoices
        self.m_hook = select_hook
        self.m_resetSelection = reset_selection
        self.m_caseSensitive = case_sensitive
        self.m_choice = None

        if title:
            self.setTitle( title)
        lay = QVBoxLayout()

        if text_widget:
            self.m_field = text_widget
        else:
            self.m_field = QLineEdit()
            lay.addWidget( self.m_field )
        self.m_field.textEdited.connect( self.processInput )

        self.m_list = QListWidget()

        self.m_list.addItems( self.m_initialChoices )
        self.m_list.clicked.connect( self.itemSelected )
        lay.addWidget( self.m_list )

        self.setLayout( lay )

    def addChoice( self, choice: str ):
        if not choice in self.m_initialChoices:
            self.m_initialChoices.append( choice )
            if self.m_sort:
                self.m_initialChoices = sorted( self.m_initialChoices )

            self.m_list.clear()
            self.m_list.addItems( self.m_initialChoices )

    def removeChoice( self, choice: str ):
        if choice in self.m_initialChoices:
            self.m_initialChoices.remove( choice )
            self.m_list.clear()
            self.m_list.addItems( self.m_initialChoices )

    def processInput( self, input ):
        self.m_list.clear()
        if not input:
            self.m_currentChoices = self.m_initialChoices
        else:
            if not self.m_currentChoices:
                self.m_currentChoices = self.m_initialChoices

            if not self.m_caseSensitive:
                input = input.lower()
                self.m_currentChoices = [ s for s in self.m_currentChoices if not s.lower().find( input ) == -1 ]
            else:
                self.m_currentChoices = [ s for s in self.m_currentChoices if not s.find( input ) == -1 ]

        self.m_list.addItems( self.m_currentChoices )

    def itemSelected( self, item ):
        i = item.row()
        text = self.m_currentChoices[ i ]
        self.reset()

        items = self.m_list.findItems( text, Qt.MatchExactly )
        if len( items ):
            items[ 0 ].setSelected( True )
            text_s = '' if self.m_resetSelection else text
            self.m_field.setText( text_s )

        self.m_choice = text
        if self.m_hook:
            self.m_hook( text )

    def choice( self ) -> str:
        return self.m_choice

    def reset( self ):
        if not self.m_currentChoices == self.m_initialChoices:
            self.m_currentChoices = self.m_initialChoices
            self.m_list.clear()
            self.m_list.addItems( self.m_initialChoices )

# class UxTreeViewer( QTreeWidget ):
#     s_labelMaxLength    = 40
#
#     def __init__( self, dir: Directory, select_hook = None, label_max_length = -1, expand = False, **kwargs ):
#         super().__init__()
#         if label_max_length < 0:
#             label_max_length = self.s_labelMaxLength
#
#         self.m_dir = dir
#         self.m_selectHook = select_hook
#
#         dir_value = dir.dir_value()
#         dir_name = dir.dir_name()
#         if dir_value and dir_name and dir_name != dir_value:
#             num_cols = 2
#             header_labels = [ dir.dir_name(), 'Description' ]
#         else:
#             num_cols = 1
#             header_labels = [ dir.show_value() ]
#
#         self.m_numCols = num_cols
#         self.setColumnCount( num_cols )
#         self.setHeaderLabels( header_labels )
#         self.itemClicked.connect( self.typeTreeItemClicked )
#
#         for subdir in dir.dir_members().values():  # -- without the root!
#             self.createTree( subdir, self, label_max_length, num_cols )
#
#         if expand:
#             for i in range( self.topLevelItemCount() ):
#                 top = self.topLevelItem( i )
#                 top.setExpanded( True )
#
#         self.resizeColumnToContents( 0 )
#         if num_cols == 2:
#             self.resizeColumnToContents( 1 )
#         self.setSizePolicy( QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding )
#
#     class TreeItem( QTreeWidgetItem ):
#         def __init__( self, parent_node, dir: Directory ):
#             super().__init__( parent_node )
#             self.m_dir = dir
#
#         def dir( self ):    return self.m_dir
#
#     @classmethod
#     def createTree( cls, dir: Directory, parent_node, label_max_length: int, num_cols: int ):
#         node = cls.TreeItem( parent_node, dir )
#         show_value = dir.show_value()
#         node.setText( 0, show_value )
#         if num_cols == 2:
#             label = dir.dir_name()
#             if label and label != show_value:
#                 if len( label ) > label_max_length:
#                     label = label[ :label_max_length ] + '...'
#
#                 node.setText( 1, label )
#
#         node.setToolTip( num_cols - 1, dir.dir_name() )
#
#         for subdir in dir.dir_members().values():
#             cls.createTree( subdir, node, label_max_length, num_cols )
#
#     def typeTreeItemClicked( self, item: QTreeWidgetItem ):
#         self.onTagSelected( item.dir() )
#
#     def onTagSelected( self, dir: Directory ):
#         if self.m_selectHook:
#             self.m_selectHook( dir )

# class UxPixmap:
#     COLOR_AUTO      = Qt.ColorScheme.AutoColor
#     COLOR_DITHER    = Qt.ColorScheme.ColorOnly
#     COLOR_MONO      = Qt.ColorScheme.MonoOnly
#     RATIO_IGNORE    = Qt.ColorScheme.IgnoreAspectRatio
#     RATIO_KEEP      = Qt.ColorScheme.KeepAspectRatio
#     RATIO_KEEP_EXP  = Qt.ColorScheme.KeepAspectRatioByExpanding
#
#     s_sourceTypeMap = {
#         str:        QPixmap.load,
#         bytes:      QPixmap.loadFromData,
#         bytearray:  QPixmap.loadFromData,
#     }
#     def __init__( self, source = None, image_format = '', color_flags = COLOR_AUTO ):
#         self.m_pixmap = QPixmap()
#         rc = self.load( source, image_format = image_format, color_flags = color_flags )
#         if not rc:
#             raise RuntimeError( rc.err() )
#
#     def load( self, source, image_format = '', color_flags = COLOR_AUTO ) -> RC:
#         if not source:
#             return RC( True )
#
#         method = self.s_sourceTypeMap.get( type( source ) )
#         if not method:
#             return RC( False, f'UxPixmap - unknown type of source = {type( source )}' )
#
#         rc = method( self.m_pixmap, source, format = image_format, flags = color_flags )
#         if not rc:
#             return RC( False, f'UxPixmap - failed to initialize from source = {source}' )
#
#         return RC( True )
#
#     def _toData( self, array: bytearray, format = '', quality = -1 ) -> bool:
#         buffer = QBuffer( array )
#         buffer.open( QIODevice.WriteOnly )
#         return self.m_pixmap.save( buffer, format = format, quality = quality )
#
#     s_destinationTypeMap = {
#         str:        QPixmap.save,
#         bytearray:  _toData,
#     }
#     def save( self, destination, color_format = '', quality = -1 ) -> RC:
#         method = self.s_destinationTypeMap.get( type( destination ) )
#         if not method:
#             return RC( False, f'UxPixmap - unknown destination type = {type( destination )}' )
#
#         rc = method( self, destination, format = color_format, quality = quality )
#         if not rc:
#             return RC( False, f'UxPixmap - failed to save to destination = {destination}' )
#
#         return RC( True )
#
#     def render( self, label: QLabel, w = 0, h = 0, scaled = RATIO_IGNORE, smooth = True ):
#         transform_mode = Qt.SmoothTransformation if smooth else Qt.FastTransformation
#         pixmap = self.m_pixmap
#         if w > 0 and h > 0:
#             pixmap = pixmap.scaled( w, h, aspectRatioMode = scaled, transformMode = transform_mode )
#         label.setPixmap( pixmap )

@singleton
class UxClipBoard:
    def __init__(self):
        self.dir = {}
        self.entity = None
        self.trait_name = ''

    # def copy(self, tag: str, value):
    #     self.dir[tag] = value
    #
    # def paste(self, tag: str):
    #     return self.dir.get(tag)
    #
    # def clear(self):
    #     self.dir = {}
    #
    # def default_tag( self ) -> str:
    #     assert self.entity and self.trait_name, 'entity and trait name are not defined'
    #
    #     cls = self.entity.__class__
    #     trait = cls.trait(self.trait_name)
    #     assert trait, f"{cls}: unknown trait '{self.trait_name}'"
    #     #tag_label = trait.label if trait.label else self.trait_name
    #     tag_label = self.trait_name
    #     return f"{self.entity}: '{tag_label}'"
    #
    # def layout(self) -> QWidget:
    #     w = QWidget()
    #     lay = QVBoxLayout()
    #     w.setLayout(lay)
    #
    #     add_row = QHBoxLayout()
    #     add_b = uxPushButton('Add', callback = self.onCopy)
    #     self.m_addNameWidget = add_name = QLineEdit()
    #     add_name.setText(self.default_tag())
    #     add_row.addWidget(add_b)
    #     add_row.addWidget(add_name)
    #     lay.addLayout(add_row)
    #
    #     lay.addWidget(uxSeparator())
    #
    #     self.m_sl = sl = UxSearchableList(choices = list( self.dir.keys() ), select_hook = self.onPaste, title = 'Use Data')
    #     lay.addWidget(sl)
    #
    #     return w
    #
    # def popup(self, parent_widget: QWidget, entity, trait_name: str):
    #     self.m_parent = parent_widget
    #     self.entity = entity
    #     self.trait_name = trait_name
    #     self.m_d = d = UxDialog(self.layout(), parent = parent_widget, cancel = '', title = 'Copy or Paste Data')
    #     d.exec()
    #
    # def onCopy(self):
    #     name = self.m_addNameWidget.text()
    #     if name:
    #         value = self.entity.get_value( self.trait_name )
    #         if value is not None:
    #             self.copy( name, value )
    #
    #     self.m_d.close()
    #
    # def onPaste( self, name: str ):
    #     value = self.paste( name )
    #     if value is not None:
    #         rc = self.m_entity.setValue( self.m_traitName, value )
    #         if not rc:
    #             uxWarning(
    #                 f"Data '{name}' is not suitable for '{self.m_entity.trait( self.m_traitName ).m_label}'",
    #                 parent = self.m_parent,
    #                 title = 'Invalid Data'
    #             )
    #
    #     self.m_d.close()

@cache
def uxInit(style = '') -> QApplication:
    if not style:
       style = platform.system()

    app = QApplication([])
    app.setStyle(style)
    return app

