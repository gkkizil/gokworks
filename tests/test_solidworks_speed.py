from unittest.mock import Mock

import pytest

from solidworks import speed


@pytest.mark.parametrize('original', [False, True])
def test_cad_job_restores_original_flag_after_failure(monkeypatch, original):
    dynamic = pytest.importorskip('win32com.client.dynamic')
    uninitialize = Mock()
    initialize = Mock(return_value=uninitialize)
    monkeypatch.setattr(speed, '_hold_apartment', initialize)
    app = Mock(CommandInProgress=original)
    connect = Mock(return_value=app)
    monkeypatch.setattr(dynamic, 'Dispatch', connect)

    with pytest.raises(RuntimeError, match='CAD job failed'):
        with speed.cad_job():
            connect.assert_not_called()
            speed.enable_for('existing dispatch')
            assert app.CommandInProgress is True
            with speed.cad_job():
                speed.enable_for('existing dispatch')
            assert app.CommandInProgress is True
            raise RuntimeError('CAD job failed')

    assert app.CommandInProgress is original
    connect.assert_called_once_with('existing dispatch')
    initialize.assert_called_once()
    uninitialize.assert_called_once()
