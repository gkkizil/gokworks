"""Test-wide defaults shared by Linux and native Windows runs."""

import os

# Tests measure geometry and grab windows right after navigation. Keep page
# transitions off so results do not depend on animation timing; the dedicated
# transition tests opt in explicitly.
os.environ.setdefault('GOKWORKS_PAGE_TRANSITIONS', '0')


import pytest


@pytest.fixture(autouse=True)
def _unanswered_unsaved_question_fails_fast(monkeypatch):
    """A test must answer the Save / Continue / Cancel question itself; a modal box would hang."""
    try:
        from gui_qt import projects
    except ImportError:          # PySide6 missing: no Qt pages in this run
        yield; return
    def unanswered(page, action):
        raise AssertionError(f'Kaydedilmemiş çalışma sorusu cevaplanmadı: {page.project_title} / {action}. '
                             'Testte gui_qt.projects.ask yerine bir cevap verin.')
    monkeypatch.setattr(projects, 'ask', unanswered)
    yield
