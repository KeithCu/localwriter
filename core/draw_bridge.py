"""In-process UNO bridge for LibreOffice Draw."""

import uno
import logging

logger = logging.getLogger(__name__)

class DrawBridge:
    def __init__(self, ctx):
        self.ctx = ctx
        self.smgr = ctx.getServiceManager()
        self.desktop = self.smgr.createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx)

    def get_active_document(self):
        doc = self.desktop.getCurrentComponent()
        if doc is None:
            raise RuntimeError("No active LibreOffice document found.")
        return doc

    def is_draw_doc(self, doc):
        return hasattr(doc, "getDrawPages")

    def get_pages(self, doc=None):
        if doc is None:
            doc = self.get_active_document()
        if not self.is_draw_doc(doc):
            raise RuntimeError("Active document is not a Draw/Impress document.")
        return doc.getDrawPages()

    def get_active_page(self, doc=None):
        if doc is None:
            doc = self.get_active_document()
        controller = doc.getCurrentController()
        if hasattr(controller, "getCurrentPage"):
            return controller.getCurrentPage()
        # Fallback to first page
        pages = self.get_pages(doc)
        if pages.getCount() > 0:
            return pages.getByIndex(0)
        return None

    def create_shape(self, shape_type, x, y, width, height, page=None):
        """
        Creates a shape of specified type and adds it to the page.
        shape_type: e.g. "com.sun.star.drawing.RectangleShape"
        """
        doc = self.get_active_document()
        if page is None:
            page = self.get_active_page(doc)
        
        shape = doc.createInstance(shape_type)
        page.add(shape)
        
        # Set size and position
        from com.sun.star.awt import Size, Point
        shape.setSize(Size(width, height))
        shape.setPosition(Point(x, y))
        return shape

    def get_shapes(self, page=None):
        if page is None:
            page = self.get_active_page()
        shapes = []
        for i in range(page.getCount()):
            shapes.append(page.getByIndex(i))
        return shapes
