"""Shared column resize behaviour (ColumnFitter) for every table and tree."""

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import QHeaderView, QTableView, QTreeView

from gui_qt.components import configure_view, fit_columns
from gui_qt.settings import SettingsStore


class Model(QAbstractTableModel):
    def __init__(self, columns=('Parça', 'Kalınlık', 'Malzeme', 'Açıklama'), rows=None):
        super().__init__()
        self.columns = columns
        self.rows = rows or [('P-1', '2', 'S235JR', 'kısa'), ('P-2', '3', 'AISI 304', 'uzun bir açıklama')]

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.columns)

    def data(self, index, role=Qt.DisplayRole):
        return self.rows[index.row()][index.column()] if role == Qt.DisplayRole else None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        return self.columns[section] if orientation == Qt.Horizontal and role == Qt.DisplayRole else None


def table(qtbot, width=640, **options):
    view = QTableView(); view.setModel(Model()); view.resize(width, 240)
    qtbot.addWidget(view); view.show()
    fitter = fit_columns(view, **options)
    qtbot.waitExposed(view); qtbot.wait(20)
    return view, view.horizontalHeader(), fitter


def used(header):
    return sum(header.sectionSize(c) for c in range(header.count()) if not header.isSectionHidden(c))


def test_every_column_is_draggable_and_the_elastic_column_fills_the_view(qtbot):
    view, header, _ = table(qtbot, elastic=0, minimum=100, fixed=(2,))
    assert all(header.sectionResizeMode(c) == QHeaderView.Interactive for c in (0, 1, 3))
    assert header.sectionResizeMode(2) == QHeaderView.Fixed
    assert not header.stretchLastSection()
    assert used(header) == view.viewport().width()
    assert view.horizontalScrollBar().maximum() == 0


def test_dragging_a_column_keeps_the_table_inside_the_view(qtbot):
    view, header, _ = table(qtbot, elastic=0, minimum=100)
    header.resizeSection(1, header.sectionSize(1) + 60)
    assert used(header) == view.viewport().width()
    header.resizeSection(3, 30)
    assert used(header) == view.viewport().width() and header.sectionSize(3) == 30


def test_dragging_the_elastic_edge_moves_the_boundary_with_its_neighbour(qtbot):
    view, header, _ = table(qtbot, elastic=0, minimum=100)
    before, neighbour = header.sectionSize(0), header.sectionSize(1)
    header.resizeSection(0, before - 40)
    assert header.sectionSize(1) == neighbour + 40
    assert used(header) == view.viewport().width()


def test_a_narrow_view_scrolls_instead_of_clipping_the_elastic_column(qtbot):
    view, header, _ = table(qtbot, width=260, elastic=0, minimum=170)
    assert header.sectionSize(0) == 170
    assert view.horizontalScrollBar().maximum() > 0


def test_view_resize_refits_and_double_click_fits_contents(qtbot):
    view, header, fitter = table(qtbot, elastic=3, minimum=80)
    view.resize(900, 240); qtbot.wait(20)
    assert used(header) == view.viewport().width()
    fitter.fit_to_contents(0)
    assert header.sectionSize(0) >= view.sizeHintForColumn(0)
    assert used(header) == view.viewport().width()


def test_user_widths_persist_and_reset_restores_defaults(qtbot, tmp_path):
    settings = SettingsStore(tmp_path / 'settings.json')
    view, header, fitter = table(qtbot, elastic=0, minimum=100, defaults={1: 90, 2: 90, 3: 90},
                                 settings=settings, key='test.table')
    header.resizeSection(2, 150)
    fitter._save()
    assert settings.get('columns/test.table') == {'2': 150}
    again, header2, _ = table(qtbot, elastic=0, minimum=100, defaults={1: 90, 2: 90, 3: 90},
                              settings=settings, key='test.table')
    assert header2.sectionSize(2) == 150
    fitter.reset()
    assert header.sectionSize(2) == 90 and settings.get('columns/test.table') == {}


def test_invalid_saved_widths_are_ignored(qtbot, tmp_path):
    settings = SettingsStore(tmp_path / 'settings.json')
    settings.set('columns/bad', {'2': 5, '1': 'x', 'z': 100, '9': 100, '3': True})
    view, header, _ = table(qtbot, elastic=0, defaults={1: 90, 2: 90, 3: 90}, settings=settings, key='bad')
    assert [header.sectionSize(c) for c in (1, 2, 3)] == [90, 90, 90]


def test_configure_view_works_when_the_model_arrives_later(qtbot):
    view = configure_view(QTreeView()); view.resize(600, 200); qtbot.addWidget(view); view.show()
    view.setModel(Model()); qtbot.waitExposed(view); qtbot.wait(20)
    header = view.header()
    assert header.count() == 4 and not header.stretchLastSection()
    assert all(header.sectionResizeMode(c) == QHeaderView.Interactive for c in range(4))
    assert used(header) == view.viewport().width()
    assert all(header.sectionSize(c) >= 60 for c in range(3))


def test_every_table_and_tree_in_the_app_uses_the_shared_behaviour(qtbot, tmp_path):
    from gui_qt.app import MainWindow, create_application
    create_application([])
    window = MainWindow(tmp_path / 'settings.json'); qtbot.addWidget(window); window.show()
    problems = []
    for key in list(window.pages):
        window.navigate(key)
        page = window.pages[key]
        for view in page.findChildren(QTableView) + page.findChildren(QTreeView):
            if not view.isVisibleTo(page) or not hasattr(view, 'horizontalHeader') and not isinstance(view, QTreeView):
                continue
            header = view.header() if isinstance(view, QTreeView) else view.horizontalHeader()
            if header.isHidden() or header.count() < 2:
                continue
            name = f'{key}:{view.accessibleName() or type(view).__name__}'
            if getattr(view, 'column_fitter', None) is None:
                problems.append(name + ' has no ColumnFitter')
            if header.stretchLastSection() or any(header.sectionResizeMode(c) in (QHeaderView.Stretch, QHeaderView.ResizeToContents)
                                                  for c in range(header.count())):
                problems.append(name + ' has non-draggable columns')
    assert not problems, problems
