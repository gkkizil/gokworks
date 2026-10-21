"""Sheet-metal export's entry point in the shared Qt transfer workspace."""

from gui_qt.export import ExportPage


class DxfDwgPage(ExportPage):
    def __init__(self, context):
        super().__init__(context, 'dxf_dwg')
