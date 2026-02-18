# from PyQt5.QtCore import QModelIndex, QPointF, QRect, QSize, Qt, QVariant
# from PyQt5.QtGui import QFont, QFontMetrics, QPainter, QPaintEvent
# from PyQt5.QtWidgets import QStyle, QStyleOptionHeader

from ui_10x.platform import ux
from ui_10x.traitable_view import TraitableView


class HeaderModel(ux.StandardItemModel):
    def _create_subtree(self, traits: dict, root: ux.StandardItem, tree: dict):
        col = 0
        for subtree_name, subtree in tree.items():
            if isinstance(subtree, str):
                trait = traits.get(subtree_name)
                if not trait:
                    continue
                label = subtree
                subtree = None
            elif isinstance(subtree, dict):
                label = subtree_name
            else:
                continue

            item = ux.StandardItem(label)
            if subtree:
                self._create_subtree(traits, item, subtree)

            if root:
                root.append_column((item, ))
            else:
                self.set_item(0, col, item)

            col += 1

    def __init__(self, traits: dict, header_structure: dict):
        super().__init__()
        self.traits = traits
        self.header_structure = header_structure
        self.create(header_structure)

    def create(self, header_structure: dict):
        self._create_subtree(self.traits, None, header_structure)

    def leaf_index(self, section_index: int) -> ux.ModelIndex:
        current_leaf_index = -1
        for i in range(self.column_count()):
            res, current_leaf_index = self.find_leaf(self.index( 0, i), section_index, current_leaf_index)
            if res.is_valid():
                return res

        return ux.ModelIndex()

    @staticmethod
    def leftmost_leaf(index: ux.ModelIndex) -> ux.ModelIndex:
        prev_index = index
        while index.is_valid():
            prev_index = index
            index = index.child(0, 0)
        return prev_index

    @staticmethod
    def find_leaf(current_index: ux.ModelIndex, section_index: int, current_leaf_index: int) -> tuple:  #-- ( index, current_leaf_index )
        if current_index.is_valid():
            child_count = current_index.model().column_count(current_index)
            if child_count:
                for i in range(child_count):
                    res, current_leaf_index = HeaderModel.find_leaf(current_index.child(0, i), section_index, current_leaf_index)
                    if res.is_valid():
                        return (res, current_leaf_index)
            else:
                current_leaf_index += 1
                if current_leaf_index == section_index:
                    return (current_index, current_leaf_index)

        return (ux.ModelIndex(), current_leaf_index)

    @staticmethod
    def search_leaves(current_index: ux.ModelIndex) -> list:
        res = []
        if current_index.is_valid():
            if not current_index.child(0, 0).is_valid():
                res.append(current_index)
            else:
                c = 0
                child = current_index.child(0, c)
                while child.is_valid():
                    found = HeaderModel.search_leaves(child)
                    res.extend(found)
                    c += 1
                    child = current_index.child(0, c)

        return res

    @staticmethod
    def leaves(search_index: ux.ModelIndex ) -> list:
        leaves = []
        if search_index.is_valid():
            child_count = search_index.model().column_count(search_index)
            for i in range(child_count):
                found = HeaderModel.search_leaves(search_index.child(0, i))
                leaves.extend(found)

        return leaves

    @staticmethod
    def find_root_index(index: ux.ModelIndex) -> ux.ModelIndex:
        while index.parent().is_valid():
            index = index.parent()
        return index

    @staticmethod
    def parent_indexes(index: ux.ModelIndex) -> list:
        indexes = []
        while index.is_valid():
            indexes.insert(0, index)
            index = index.parent()
        return indexes


class HeaderView(ux.HeaderView):
    def __init__(self, view: TraitableView, parent: ux.Widget = None):
        super().__init__(ux.Horizontal, parent = parent)
        self.m_model = HeaderModel(view.ui_hints, view.header)
        self.set_model(self.m_model)

        #self.setStretchLastSection(False)
        self.setSectionResizeMode(ux.HeaderView.ResizeMode.Stretch)

        self.painted_cells = set()
        ##self.section_resized_connect(self.on_section_resized)

    def set_foreground_brush(self, opt: ux.StyleOptionHeader, index: ux.ModelIndex ):
        fgb = index.data(ux.ForegroundRole)
        if fgb:
            opt.palette.set_brush(ux.Palette.ButtonText, fgb)

    def set_background_brush(self, opt: ux.StyleOptionHeader, index: ux.ModelIndex ):
        bgb = index.data(ux.BackgroundRole)
        if bgb:
            opt.palette.set_brush(ux.Palette.Button, bgb)
            opt.palette.set_brush(ux.Palette.Window, bgb)


    # s_selected_position = (
    #     ux.StyleOptionHeader.NotAdjacent,                     # prev - 0, next 0
    #     ux.StyleOptionHeader.NextIsSelected,                  # prev - 0, next 1
    #     ux.StyleOptionHeader.PreviousIsSelected,              # prev - 1, next 0
    #     ux.StyleOptionHeader.NextAndPreviousAreSelected       # prev - 1, next 1
    # )
    def style_option_for_cell(self, logical_index: int) -> ux.StyleOptionHeader:
        opt = ux.StyleOptionHeader()
        # self.init_style_option(opt)
        # if self.window().is_active_window():
        #     opt.state |= ux.Style.State_Active
        # opt.text_alignment = ux.AlignCenter
        # opt.icon_alignment = ux.AlignVCenter
        # opt.section = logical_index
        #
        # visual = self.visual_index(logical_index)
        #
        # if self.count() == 1:
        #     opt.position = ux.StyleOptionHeader.OnlyOneSection
        # else:
        #     if visual == 0:
        #         opt.position = QStyleOptionHeader.Beginning
        #     else:
        #         opt.position = QStyleOptionHeader.End if visual == ( self.count() - 1 ) else QStyleOptionHeader.Middle
        #
        # if self.sectionsClickable():
        #     if self.highlightSections() and self.selectionMode():
        #         if self.selectionModel().columnIntersectsSelection( logical_index, self.rootIndex() ):
        #             opt.state |= QStyle.State_On
        #         if self.selectionModel().isColumnSelected( logical_index, self.rootIndex() ):
        #             opt.state |= QStyle.State_Sunken
        #
        # if self.selectionModel():
        #     prev_selected = self.selectionModel().isColumnSelected( self.logicalIndex( visual - 1 ), self.rootIndex() )
        #     next_selected = self.selectionModel().isColumnSelected( self.logicalIndex( visual + 1 ), self.rootIndex() )
        #     code = 2 * prev_selected + next_selected
        #     opt.selectedPosition = self.s_selectedPosition[ code ]

        return opt

    # def cell_size(self, leaf_index: ux.ModelIndex, style_options: ux.StyleOptionHeader) -> ux.Size:
    #     res = ux.Size()
    #     variant = QVariant(leaf_index.data(Qt.SizeHintRole))
    #     if variant.isValid():
    #         res = variant   # TODO: cast?
    #     fnt = QFont(self.font())
    #     var = QVariant(leaf_index.data(Qt.FontRole))
    #     if var.isValid():
    #         fnt = var
    #     fnt.setBold(True)
    #     fm = QFontMetrics(fnt)
    #     size = QSize(fm.size(0, leaf_index.data(Qt.DisplayRole)))
    #     if leaf_index.data(Qt.UserRole):      # isValid()
    #         size.transpose()
    #     decoration_size = self.style().sizeFromContents(QStyle.CT_HeaderSection, style_options, QSize(), self)
    #     empty_text_size = QSize(fm.size( 0, '' ))
    #     return res.expandedTo(size + decoration_size - empty_text_size)
    #
    # def current_cell_width(self, searched_index: QModelIndex, leaf_index: QModelIndex, section_index: int) -> int:
    #     leaves = HeaderModel.leaves(searched_index)
    #     if not leaves:
    #         return self.section_size(section_index)
    #
    #     first_leaf_section_index = section_index - leaves.index(leaf_index)
    #     return sum(self.section_size(first_leaf_section_index + i) for i in range(len(leaves)))
    #
    # def current_cell_left(self, searched_index: QModelIndex, leaf_index: QModelIndex, section_index: int, left: int) -> int:
    #     leaves = HeaderModel.leaves(searched_index)
    #     if leaves:
    #         n = leaves.index(leaf_index)
    #         first_leaf_section_index = section_index - n
    #         n -= 1
    #         left -= sum(self.section_size(first_leaf_section_index + i) for i in range(n))
    #     return left
    #
    # def paint_horizontal_cell(self, painter: QPainter, cell_index: QModelIndex, leaf_index: QModelIndex, logical_index: int, style_options: QStyleOptionHeader, section_rect: QRect, top: int) -> int:
    #     uniopt = QStyleOptionHeader(style_options)
    #     self.set_foreground_brush(uniopt, cell_index)
    #     self.set_background_brush(uniopt, cell_index)   # TODO!
    #
    #     height = self.cell_size(cell_index, uniopt).height()
    #
    #     if cell_index == leaf_index:
    #         height = section_rect.height() - top
    #
    #     left    = self.current_cell_left(cell_index, leaf_index, logical_index, section_rect.left())
    #     width   = self.current_cell_width(cell_index, leaf_index, logical_index)
    #
    #     if cell_index not in self.painted_cells:
    #         self.painted_cells.add(cell_index)
    #         r = QRect(left, top, width, height)
    #
    #         uniopt.text = cell_index.data(Qt.DisplayRole)
    #         painter.save()
    #         uniopt.rect = r
    #         self.style().drawControl(QStyle.CE_Header, uniopt, painter, self)
    #
    #         painter.restore()
    #
    #     return top + height
    #
    # def paintEvent(self, event: QPaintEvent):
    #     self.painted_cells = set()
    #     super().paintEvent(event)
    #
    # def paintSection(self, painter: QPainter, rect: QRect, logical_index: int):
    #     if rect.isValid():
    #         leaf_index = self.model.leaf_index(logical_index)
    #         if leaf_index.is_valid():
    #             old_bo = QPointF(painter.brushOrigin())
    #             top = rect.y()
    #             indexes = HeaderModel.parent_indexes(leaf_index)
    #             style_options = self.style_option_for_cell(logical_index)
    #             for i in range(len(indexes)):
    #                 real_style_options = QStyleOptionHeader(style_options)
    #                 state = int(real_style_options.state)
    #                 if i < (len(indexes) - 1) and (bool(state & QStyle.State_Sunken) or bool(state & QStyle.State_On)):
    #                     real_style_options.state &= ~(QStyle.State_Sunken | QStyle.State_On)
    #
    #                 cell = indexes[i]
    #                 top = self.paint_horizontal_cell(painter, cell, leaf_index, logical_index, real_style_options, rect, top)
    #
    #             painter.setBrushOrigin(old_bo)
    #             return
    #
    #     super().paintSection(painter, rect, logical_index)
    #
    # def sectionSizeFromContents(self, logical_index: int ) -> QSize:
    #     cur_leaf_index = QModelIndex(self.model.leaf_index(logical_index))
    #     if not cur_leaf_index.is_valid():
    #         return super().sectionSizeFromContents(logical_index)
    #
    #     style_option = QStyleOptionHeader(self.style_option_for_cell(logical_index ))
    #     s = QSize(self.cell_size(cur_leaf_index, style_option))
    #     cur_leaf_index = cur_leaf_index.parent()
    #     while cur_leaf_index.is_valid():
    #         s.setHeight(s.height() + self.cell_size(cur_leaf_index, style_option).height())
    #         cur_leaf_index = cur_leaf_index.parent()
    #
    #     return s
    #
    # def on_section_resized(self, logical_index: int, i2, i3 ):
    #     if self.is_section_hidden(logical_index):
    #         return
    #
    #     leaf_index = QModelIndex(self.model.leaf_index(logical_index))
    #     if leaf_index.is_valid():
    #         root_index = HeaderModel.find_root_index(leaf_index)
    #         leaves = HeaderModel.leaves(root_index)
    #         try:
    #             n = leaves.index(leaf_index)
    #             while n > 0:
    #                 logical_index -= 1
    #
    #                 w = self.viewport().width()
    #                 h = self.viewport().height()
    #                 pos = self.sectionViewportPosition(logical_index)
    #                 r = QRect(pos, 0, w - pos, h)
    #                 if self.isRightToLeft():
    #                     r.setRect(0, 0, pos + self.sectionSize(logical_index), h)
    #
    #                 self.viewport().update( r.normalized() )
    #                 n -= 1
    #         except Exception:
    #             pass
