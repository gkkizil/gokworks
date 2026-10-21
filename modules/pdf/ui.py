"""PDF export's entry point in the shared Qt transfer workspace."""

from gui_qt.export import ExportPage


class PdfPage(ExportPage):
    def __init__(self, context):
        super().__init__(context, 'pdf')
