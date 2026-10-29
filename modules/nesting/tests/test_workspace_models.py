"""Tree adapters preserve source identity through grouping, filtering and sorting."""

from PySide6.QtCore import Qt
from gui_qt.models import FilterProxy,Column
from modules.nesting.ui_widgets import NestingTableModel
from modules.nesting.workspace_models import PartTreeModel,PartTree


def source():
    model=NestingTableModel([Column('Parça','display_code'),Column('Adet','quantity'),Column('t','thickness')])
    model.replace([dict(id='a',display_code='Alpha',quantity=2,thickness=2,material='S235JR',kind='part'),
        dict(id='b',display_code='Beta',quantity=3,thickness=3,material='S235JR',kind='part'),
        dict(id='c',display_code='Gamma',quantity=4,thickness=2,material='S355JR',kind='part'),
        dict(id='bad',display_code='Broken',quantity=None,thickness=2,material='S235JR',kind='import')])
    proxy=FilterProxy();proxy.setSourceModel(model)
    return model,proxy


def test_tree_satisfies_native_model_contract_and_maps_each_real_row_once(qtmodeltester):
    model,proxy=source();tree=PartTreeModel(proxy)
    qtmodeltester.check(tree)
    assert tree.rowCount()==4
    seen=[]
    for group in range(tree.rowCount()):
        parent=tree.index(group,0)
        assert not tree.flags(parent)&Qt.ItemIsSelectable
        for row in range(tree.rowCount(parent)):
            leaf=tree.index(row,0,parent);seen.append(leaf.data(Qt.UserRole)['id'])
            assert tree.parent(leaf)==parent and tree.mapFromSource(tree.mapToSource(leaf))==leaf
    assert sorted(seen)==['a','b','bad','c']
    proxy.set_query('Alpha');assert tree.rowCount()==1 and len(tree.by_id)==1
    proxy.set_query('');proxy.sort(0,Qt.DescendingOrder)
    assert sorted(tree.by_id)==['a','b','bad','c']
    model.replace([]);assert tree.rowCount()==0 and not tree.index(0,0).isValid()


def test_tree_retains_the_actual_id_after_source_sort_and_clears_filtered_selection(qtbot):
    model,proxy=source();tree=PartTreeModel(proxy);view=PartTree();qtbot.addWidget(view)
    view.setModel(tree);view.show();view.select_index(tree.index_for_id('a'))
    proxy.sort(0,Qt.DescendingOrder)
    assert view.currentIndex().data(Qt.UserRole)['id']=='a'
    assert [i.data(Qt.UserRole)['id'] for i in view.selectionModel().selectedRows()]==['a']
    proxy.set_query('Beta');assert not view.selectionModel().selectedRows()
    assert tree.index_for_id('b').isValid() and not tree.index_for_id('a').isValid()
