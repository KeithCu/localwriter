"""Bridge for Draw/Impress documents."""

import logging

log = logging.getLogger("localwriter.draw")


class DrawBridge:
    def __init__(self, doc):
        self.doc = doc
        if not hasattr(doc, "getDrawPages"):
            raise RuntimeError("Not a Draw/Impress document.")

    def get_pages(self):
        return self.doc.getDrawPages()

    def get_active_page(self):
        controller = self.doc.getCurrentController()
        if hasattr(controller, "getCurrentPage"):
            return controller.getCurrentPage()
        pages = self.get_pages()
        if pages.getCount() > 0:
            return pages.getByIndex(0)
        return None

    def create_shape(self, shape_type, x, y, width, height, page=None):
        if page is None:
            page = self.get_active_page()
        shape = self.doc.createInstance(shape_type)
        page.add(shape)
        from com.sun.star.awt import Size, Point
        shape.setSize(Size(width, height))
        shape.setPosition(Point(x, y))
        return shape

    def create_slide(self, index=None):
        pages = self.get_pages()
        if index is None:
            index = pages.getCount()
        return pages.insertNewByIndex(index)

    def delete_slide(self, index):
        pages = self.get_pages()
        page = pages.getByIndex(index)
        pages.remove(page)
