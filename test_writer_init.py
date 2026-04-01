from plugin.modules.writer import WriterModule
class MockTools:
    def auto_discover_package(self, p):
        pass
class MockServices:
    def __init__(self):
        self.tools = MockTools()
    def auto_discover(self, m):
        pass

w = WriterModule()
w.initialize(MockServices())
