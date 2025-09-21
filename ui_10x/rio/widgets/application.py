from __future__ import annotations

from core_10x.named_constant import EnumBits

import ui_10x.platform_interface as i


class Style(i.Style):
    class EnumMeta(type):
        def __getattr__(cls, value):
            if value != value.upper():
                return getattr(cls, value.upper()).value

    class StandardPixmap(EnumBits, metaclass=EnumMeta):
        """Mapping of Qt QStyle::StandardPixmap values to Material Icons."""

        # Dialog Buttons
        SP_DIALOGAPPLYBUTTON = ('done',)
        SP_DIALOGCANCELBUTTON = ('close',)
        SP_DIALOGCLOSEBUTTON = ('close',)
        SP_DIALOGDISCARDBUTTON = ('close',)
        SP_DIALOGHELPBUTTON = ('help_outline',)
        SP_DIALOGNOBUTTON = ('close',)
        SP_DIALOGOKBUTTON = ('check',)
        SP_DIALOGOPENBUTTON = ('folder_open',)
        SP_DIALOGRESETBUTTON = ('restart_alt',)
        SP_DIALOGSAVEBUTTON = ('save',)
        SP_DIALOGYESBUTTON = ('check',)
        # Arrows and Navigation
        SP_ARROWBACK = ('arrow_back',)
        SP_ARROWDOWN = ('arrow_downward',)
        SP_ARROWFORWARD = ('arrow_forward',)
        SP_ARROWLEFT = ('arrow_left',)
        SP_ARROWRIGHT = ('arrow_right',)
        SP_ARROWUP = ('arrow_upward',)
        # File System and Folders
        SP_DIRCLOSEDICON = ('folder',)
        SP_DIRHOMEICON = ('home',)
        SP_DIRICON = ('folder',)
        SP_DIRLINKICON = ('folder_special',)
        SP_DIROPENICON = ('folder_open',)
        SP_FILEDIALOGBACK = ('arrow_back',)
        SP_FILEDIALOGCONTENTSVIEW = ('view_list',)
        SP_FILEDIALOGDETAILEDVIEW = ('grid_view',)
        SP_FILEDIALOGEND = ('last_page',)
        SP_FILEDIALOGINFOVIEW = ('info',)
        SP_FILEDIALOGLISTVIEW = ('list',)
        SP_FILEDIALOGNEWFOLDER = ('create_new_folder',)
        SP_FILEDIALOGSTART = ('first_page',)
        SP_FILEDIALOGTOPARENT = ('arrow_upward',)
        SP_FILEICON = ('description',)
        SP_FILELINKICON = ('insert_link',)
        # Drives and Devices
        SP_COMPUTERICON = ('computer',)
        SP_DESKTOPICON = ('desktop_windows',)
        SP_DRIVECDICON = ('album',)
        SP_DRIVEDVDICON = ('album',)
        SP_DRIVEFDICON = ('save',)
        SP_DRIVEHDICON = ('storage',)
        SP_DRIVENETICON = ('cloud',)
        SP_HOMEICON = ('home',)
        SP_TRASHICON = ('delete',)
        # Media Controls
        SP_MEDIAPAUSE = ('pause',)
        SP_MEDIAPLAY = ('play_arrow',)
        SP_MEDIASEEKBACKWARD = ('fast_rewind',)
        SP_MEDIASEEKFORWARD = ('fast_forward',)
        SP_MEDIASKIPBACKWARD = ('skip_previous',)
        SP_MEDIASKIPFORWARD = ('skip_next',)
        SP_MEDIASTOP = ('stop',)
        SP_MEDIAVOLUME = ('volume_up',)
        SP_MEDIAVOLUMEMUTED = ('volume_off',)
        # Message Boxes
        SP_MESSAGEBOXCRITICAL = ('error',)
        SP_MESSAGEBOXINFORMATION = ('info',)
        SP_MESSAGEBOXQUESTION = ('help',)
        SP_MESSAGEBOXWARNING = ('warning',)
        # Browser Controls
        SP_BROWSERRELOAD = ('refresh',)
        SP_BROWSERSTOP = ('stop',)
        # Title Bar and Window Controls
        SP_TITLEBARCLOSEBUTTON = ('close',)
        SP_TITLEBARCONTEXTHELPBUTTON = ('help_outline',)
        SP_TITLEBARMAXBUTTON = ('maximize',)
        SP_TITLEBARMENUBUTTON = ('menu',)
        SP_TITLEBARMINBUTTON = ('minimize',)
        SP_TITLEBARNORMALBUTTON = ('restore',)
        SP_TITLEBARSHADEBUTTON = ('expand_less',)
        SP_TITLEBARUNSHADEBUTTON = ('expand_more',)
        # Toolbar and Dock Widgets
        SP_DOCKWIDGETCLOSEBUTTON = ('close',)
        SP_TOOLBARHORIZONTALEXTENSIONBUTTON = ('chevron_right',)
        SP_TOOLBARVERTICALEXTENSIONBUTTON = ('chevron_down',)
        # Platform-Specific
        SP_COMMANDLINK = ('arrow_right_alt',)
        SP_VISTASHIELD = ('security',)

    def standard_icon(self, style_icon: int):
        return f'material/{self.StandardPixmap.s_reverse_dir[style_icon].label}'


class Application(i.Application):
    @classmethod
    def instance(cls) -> Application:
        raise NotImplementedError()

    @classmethod
    def style(cls):
        return Style()
