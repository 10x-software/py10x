from core_10x.directory import Directory

ANIMALS = Directory.define(
    'Animals',
    [
        'Microorganisms',
        [
            'Single Cell',
            'Multi Cell',
        ],
        'Mollusks',
        'Fishes',
        [
            'Salt Water',
            [
                'Beluga'
            ],
            'Fresh Water',
        ],
        'Amphibia',
        'Reptiles',
        'Birds',
        'Mammals',
        [
            'Cats',
            'Dogs',
            'Bears',
            'Whales',
            [
                'Bluewhale',
                'Orca',
                'Spermwhale',
                'Beluga'
            ],
        ],
    ],
)

FISH = Directory.define(
    ( 'FWF', 'Fresh Water Fish' ),
    [
        ( 'PkF',    'Pike Family' ),
        [
            ( 'NPK',    'Northern Pike' ),
            ( 'MSK',    'Muskie' ),
            ( 'PKL',    'Pickerel' ),
        ],
        ( 'PeF', 'Perch Family' ),
        [
            ( 'PCH',    'Common Perch' ),
            ( 'YPH',    'Yellow Perch' ),
            ( 'WLY',    'Walleye' ),
            ( 'SGR',    'Sagger' ),
        ],
        ( 'CrF',    'Carp Family' ),
        [
            ( 'CRP',    'Common Carp' ),
            ( 'WCP',    'Wild Carp' ),
            ( 'IDE',    'Ide' ),
            ( 'BRM',    'Bream' ),
            ( 'RCH',    'Roach' ),
        ],
    ],
)

STANDARD_PIXMAPS = Directory.define(
    'Standard Pixmaps',
    [
        'Title Bar',
        [
            'TitleBarMaxButton',
            'TitleBarCloseButton',
            'TitleBarNormalButton',
            'TitleBarShadeButton',
            'TitleBarUnshadeButton',
            'TitleBarContextHelpButton',
        ],
        'Message Box',
        [
            'MessageBoxInformation',
            'MessageBoxWarning',
            'MessageBoxCritical',
            'MessageBoxQuestion',
        ],
        'Drive',
        [
            'DriveFDIcon',
            'DriveHDIcon',
            'DriveCDIcon',
            'DriveDVDIcon',
            'DriveNetIcon',
        ],
        'Dir',
        [
            'DirHomeIcon',
            'DirOpenIcon',
            'DirClosedIcon',
            'DirIcon',
            'DirLinkIcon',
            'DirLinkOpenIcon',
        ],
        'File',
        [
            'FileIcon',
            'FileLinkIcon',
            'FileDialogStart',
            'FileDialogEnd',
            'FileDialogToParent',
            'FileDialogNewFolder',
            'FileDialogDetailedView',
            'FileDialogInfoView',
            'FileDialogContentsView',
            'FileDialogListView',
            'FileDialogBack',
        ],
        'Dialog',
        [
            'DialogOkButton',
            'DialogCancelButton',
            'DialogHelpButton',
            'DialogOpenButton',
            'DialogSaveButton',
            'DialogCloseButton',
            'DialogApplyButton',
            'DialogResetButton',
            'DialogDiscardButton',
            'DialogYesButton',
            'DialogNoButton',
            'DialogYesToAllButton',
            'DialogNoToAllButton',
            'DialogSaveAllButton',
            'DialogAbortButton',
            'DialogRetryButton',
            'DialogIgnoreButton',
        ],
        'Arrow',
        [
            'ArrowUp',
            'ArrowDown',
            'ArrowLeft',
            'ArrowRight',
            'ArrowBack',
            'ArrowRight',
            'ArrowForward',
        ],
        'Media',
        [
            'MediaPlay',
            'MediaStop',
            'MediaPause',
            'MediaSkipForward',
            'MediaSkipBackward',
            'MediaSeekForward',
            'MediaSeekBackward',
            'MediaVolume',
            'MediaVolumeMuted',
        ],
        'Other',
        [
            'DesktopIcon',
            'TrashIcon',
            'ComputerIcon',
            'DockWidgetCloseButton',
            'ToolBarHorizontalExtensionButton',
            'ToolBarVerticalExtensionButton',
            'CommandLink',
            'VistaShield',
            'BrowserReload',
            'BrowserStop',
            'LineEditClearButton',
            'RestoreDefaultsButton',
        ],
    ],
    #'CustomBase',
)

if __name__ == '__main__':
    h1 = FISH.choices()

    f = ANIMALS.flatten()
    h2 = ANIMALS.choices()
