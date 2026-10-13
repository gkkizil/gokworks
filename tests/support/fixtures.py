"""Assembly setup shared by automatic, manual and native dispatch K/R tests."""

import unittest

from k_factor import apply as ap
from support.solidworks import (
    FakeApp,
    FakeAssembly,
    FakeComponent,
    SheetPart,
    install_com,
)


class KApplyTestCase(unittest.TestCase):
    def setUp(self):
        self.model=SheetPart()
        self.assembly=FakeAssembly('/work/main.sldasm',[FakeComponent(self.model.path) for _ in range(3)])
        self.app=FakeApp(self.model,previous=self.assembly)
        self.com, self.client = install_com(self, ap, 'kr', dynamic=True)
