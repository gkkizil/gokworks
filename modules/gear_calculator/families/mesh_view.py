"""Do not requeue software rendering after the mechanism's 3D tab is hidden."""
from PySide6.QtCore import Slot
from modules.dxf_dwg.preview.viewer import MeshView


class MechanismMeshView(MeshView):
    def render(self):
        if not self.isVisible():
            self.pending=False
            return
        super().render()

    @Slot(int,object)
    def rendered(self,generation,image):
        if not self.isVisible():self.pending=False
        super().rendered(generation,image)

    def hideEvent(self,event):
        self.pending=False;self.timer.stop();self.cancel_render()
        super().hideEvent(event)

    def showEvent(self,event):
        super().showEvent(event)
        if self.mesh is not None:self.timer.start()
