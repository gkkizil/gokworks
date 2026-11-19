"""Stock on hand: offcuts first, then stock bars, then bars to buy; cutting updates the stock."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from modules.profile_cutting.models import Demand, Project
from modules.profile_cutting.optimizer import BUY, optimize, validate_plan
from modules.profile_cutting.stock import FULL, OFFCUT, Stock, apply_plan, load, match_key
from .test_ui import page  # noqa: F401


def project(*rows, stock='6000'):
    return Project([Demand(f'd{i}', p, m, l, c) for i, (p, m, l, c) in enumerate(rows)], stock, '3', '0')


def test_match_ignores_spacing_case_and_x_spelling():
    assert match_key('40 x 40 x 2', 's235jr') == match_key('40X40X2', 'S235JR') == match_key('40×40×2', 'S235JR')


def test_offcut_is_used_first_then_stock_then_bars_to_buy():
    plan = optimize(project(('40x40x2', 'S235JR', '1000', 7)),
                    stock_items=[Stock('bar', '40 x 40 x 2', 'S235JR', '3000', 1, FULL),
                                 Stock('cut', '40x40x2', 'S235JR', '1100', 1, OFFCUT)])
    validate_plan(project(('40x40x2', 'S235JR', '1000', 7)), plan)
    origins = [(b.source, b.stock_length, len(b.cuts)) for b in plan.bars]
    # 1003 mm each: the 3000 bar takes 2 (it opens first; the 1100 offcut is too short for 2 but holds 1).
    assert sorted(origins) == sorted([('Stok', '3000', 2), (OFFCUT, '1100', 1), (BUY, '6000', 4)])
    assert sum(len(b.cuts) for b in plan.bars) == 7


def test_without_matching_stock_the_proven_minimum_path_is_unchanged():
    rows = (('40x40x2', 'S235JR', '1000', 6),)
    plain = optimize(project(*rows))
    other = optimize(project(*rows), stock_items=[Stock('x', '50x50x3', 'S235JR', '6000', 5)])
    assert len(plain.bars) == len(other.bars) == 2 and plain.optimal and other.optimal
    assert all(b.source == BUY for b in other.bars)


def test_cutting_removes_used_bars_and_keeps_long_leftovers():
    items = [Stock('bar', '40x40x2', 'S235JR', '3000', 2, FULL)]
    plan = optimize(project(('40x40x2', 'S235JR', '1000', 2)), stock_items=items)
    used, added = apply_plan(items, plan, keep_from='500')
    assert used == 1 and added == 1
    assert [(i.kind, i.length, i.count) for i in items] == [(FULL, '3000', 1), (OFFCUT, '994', 1)]


def test_stock_tab_entry_parts_suggestion_plan_and_restart(page, qtbot, tmp_path, monkeypatch):  # noqa: F811
    p, w = page
    p.project.demands = [Demand('a', '40x40x2', 'S235JR', '1000', 4)]; p.refresh_demands()
    p.stock_from_parts_button.click()
    assert [(s.profile, s.length, s.count) for s in p.stocks] == [('40x40x2', '6000', 1)]
    p.stock_model.setData(p.stock_model.index(0, 3), '2', Qt.EditRole)       # type the real quantity
    assert p.stocks[0].count == 2
    p.stock_profile.setEditText('40 x 40 x 2'); p.stock_material.setEditText('s235jr')
    p.stock_length.setText('1200'); p.stock_count.setText('1'); p.stock_kind.setCurrentText(OFFCUT)
    p.stock_add_button.click()
    assert [s.kind for s in p.stocks] == [FULL, OFFCUT] and 'Stokta 2 tam boy çubuk ve 1 artık' in p.stock_summary.text()
    p.calculate(); qtbot.waitUntil(lambda: not w.jobs.busy and p.plan is not None, timeout=8000)
    assert {b.source for b in p.plan.bars} <= {'Stok', OFFCUT} and 'satın alma yok' in p.plan_summary.text()
    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **k: QMessageBox.Yes)
    p.apply_plan_to_stock()
    assert sum(s.count for s in p.stocks if s.kind == FULL) <= 2
    assert [vars(s) for s in load(w.settings)] == [vars(s) for s in p.stocks]   # saved automatically


def test_invalid_stock_entry_says_what_to_fix(page):  # noqa: F811
    p, _ = page
    p.stock_profile.setEditText(''); p.stock_add_button.click()
    assert 'profil kesiti' in p.status_text and not p.stocks
    p.stock_profile.setEditText('40x40x2'); p.stock_material.setEditText('S235JR'); p.stock_length.setText('abc')
    p.stock_add_button.click()
    assert 'Çubuk boyu' in p.status_text and not p.stocks
