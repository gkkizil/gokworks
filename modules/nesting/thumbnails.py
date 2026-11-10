"""Bounded, lazy Qt contour icons for the part list; never changes CAD data."""
from collections import OrderedDict

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPen

from .render import painter_path
from .ui_widgets import part_colors


class PartThumbnails:
    def __init__(self,limit=256):
        self.limit=limit; self.parts={}; self.records={}; self.cache=OrderedDict()
        self.revision=0; self.render_count=0

    def set_parts(self,parts):
        current={}
        for index,part in enumerate(parts):
            previous=self.records.get(part.id)
            if previous is not None and previous[0] is part.geometry:
                token=previous[1]
            else:
                self.revision+=1; token=self.revision
            current[part.id]=(part.geometry,token,index)
        self.records=current; self.parts={p.id:p for p in parts}

    def icon(self,part_id,appearance='dark',dpr=1.):
        if part_id not in self.parts: return QIcon()
        _,token,index=self.records[part_id]
        dpr=max(1.,min(float(dpr),4.))
        key=(token,index,appearance,dpr)
        if key in self.cache:
            self.cache.move_to_end(key); return self.cache[key]
        geometry=self.parts[part_id].polygon
        if geometry.is_empty or geometry.area<=0 or not geometry.is_valid: return QIcon()
        width,height=36,28
        pixmap=QPixmap(round(width*dpr),round(height*dpr)); pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.transparent)
        path=painter_path(geometry); bounds=path.boundingRect()
        if bounds.width()<=0 or bounds.height()<=0: return QIcon()
        painter=QPainter(pixmap)
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            scale=min((width-6)/bounds.width(),(height-6)/bounds.height())
            painter.translate(width/2,height/2); painter.scale(scale,scale)
            painter.translate(-bounds.center().x(),-bounds.center().y())
            fill,outline=part_colors(index,appearance)
            pen=QPen(outline); pen.setWidthF(1.2/scale)
            painter.setPen(pen); painter.setBrush(fill); painter.drawPath(path)
        finally: painter.end()
        result=QIcon(pixmap); self.cache[key]=result; self.render_count+=1
        while len(self.cache)>self.limit: self.cache.popitem(last=False)
        return result
