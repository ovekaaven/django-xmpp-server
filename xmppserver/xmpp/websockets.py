from slixmpp import Callback, StanzaPath
from slixmpp.xmlstream import StanzaBase, tostring
from .stream import StreamElement, Stream

NS_XMPP_FRAMING = 'urn:ietf:params:xml:ns:xmpp-framing'

class WSOpen(StreamElement):
    name = 'open'
    namespace = NS_XMPP_FRAMING

class WSClose(StanzaBase):
    name = 'close'
    namespace = NS_XMPP_FRAMING
    interfaces = set()

class WSStream(Stream):
    ping_keepalives = True

    def __init__(self, consumer):
        super(WSStream, self).__init__()
        self.update_logger({'transport': 'WebSockets'})
        self.consumer = consumer
        self.closing = False
        self.register_stanza(WSOpen)
        self.register_handler(
            Callback('WSOpen',
                     StanzaPath('open'),
                     self._handle_open))
        self.register_stanza(WSClose)
        self.register_handler(
            Callback('WSClose',
                     StanzaPath('close'),
                     self._handle_close))
        self.add_event_handler('session_bind',
                               self._session_bind)

    def abort(self):
        self.loop.create_task(self.consumer.close_socket())

    def send_element(self, xml):
        self.send_raw(tostring(xml, top_level=True))

    def send_raw(self, data):
        self.loop.create_task(self.consumer.send_data(data))

    async def send_init(self):
        self.stream_id = await self.generate_id()
        self.update_logger({'sid': self.stream_id})
        self.consumer.logger.info('Starting stream %s', self.stream_id)
        self.logger.debug('Starting stream')
        element = WSOpen()
        element['from'] = self.host
        element['id'] = self.stream_id
        element['version'] = self.version
        self.send(element)
        self.send_features()

    def close(self):
        if not self.closing:
            self.closing = True
            self.send(WSClose())

    def _handle_open(self, element):
        self.start_stream_handler(element.xml)

    def _handle_close(self, element):
        self.close() # sends close reply if needed
        self.abort()

    def _session_bind(self, jid):
        self.consumer.logger.info('Bound to %s', jid.full)

async def handle_ws(consumer, xml):
    if not consumer.stream:
        if xml.tag == WSOpen.tag_name():
            consumer.stream = WSStream(consumer)
            if consumer.is_trusted():
                consumer.stream.web_user = await consumer.get_user()
        else:
            # TODO: stream error?
            await consumer.close_socket()
            return
    consumer.stream.handle_stanza(xml)

async def disconnect_ws(consumer):
    if consumer.stream is not None:
        consumer.stream.connection_lost()
    consumer.stream = None
