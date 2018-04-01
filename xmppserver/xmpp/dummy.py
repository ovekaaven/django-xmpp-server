from .stream import Stream

# Dummy streams are not connected to anyone, but can be
# used to communicate with other streams, for example.

class DummyStream(Stream):
    def __init__(self):
        super(DummyStream, self).__init__()
        self.prepare_features()

    def send_element(self, xml):
        pass

    def send_raw(self, data):
        pass
