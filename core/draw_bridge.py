"""In-process UNO bridge for LibreOffice Draw."""

import uno
import logging

logger = logging.getLogger(__name__)

class DrawBridge:
    def __init__(self, doc):
        self.doc = doc
        if not hasattr(doc, "getDrawPages"):
             raise RuntimeError("Provided document is not a Draw/Impress document.")

    def get_pages(self):
        return self.doc.getDrawPages()

    def get_active_page(self):
        controller = self.doc.getCurrentController()
        if hasattr(controller, "getCurrentPage"):
            return controller.getCurrentPage()
        # Fallback to first page
        pages = self.get_pages()
        if pages.getCount() > 0:
            return pages.getByIndex(0)
        return None

    def create_shape(self, shape_type, x, y, width, height, page=None):
        """
        Creates a shape of specified type and adds it to the page.
        shape_type: e.g. "com.sun.star.drawing.RectangleShape"
        """
        if page is None:
            page = self.get_active_page()
        
        shape = self.doc.createInstance(shape_type)
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
