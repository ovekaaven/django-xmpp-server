from slixmpp import Callback, StanzaPath
from slixmpp.xmlstream.stanzabase import ET, StanzaBase, register_stanza_plugin
from slixmpp.stanza import StreamFeatures
from slixmpp.features.feature_starttls import stanza as tls_stanza
from .stream import Stream
from ..conf import settings

# tls_stanza.STARTTLS is meant as a feature flag
# and thus doesn't subclass StanzaBase, so we
# have to define the stanza ourselves here.
class StartTLS(StanzaBase):
    name = 'starttls'
    namespace = 'urn:ietf:params:xml:ns:xmpp-tls'
    interfaces = set()
    plugin_attrib = name

class TCPStream(Stream):
    def __init__(self, protocol):
        super(TCPStream, self).__init__()
        self.update_logger({'transport': 'TCP'})
        self.protocol = protocol
        self.protocol_logger = protocol.logger
        self.transport = protocol.transport
        self.tls_options = protocol.factory.options
        self.socket = None
        if self.tls_options:
            register_stanza_plugin(StreamFeatures,
                                   tls_stanza.STARTTLS)
            self.register_stanza(StartTLS)
            self.register_handler(
                Callback('STARTTLS',
                         StanzaPath('starttls'),
                         self._handle_starttls))
        self.add_event_handler('auth_success',
                               self._auth_success)
        self.add_event_handler('session_bind',
                               self._session_bind)
        self.init_parser()

    def init_parser(self):
        self.xml_depth = 0
        self.xml_root = None
        # workaround: slixmpp's xmlstream imports wrong type of ElementTree
        # (imports xml.etree.ElementTree, but stanzabase uses cElementTree)
        self.parser = ET.XMLPullParser(("start", "end"))

    async def get_features(self):
        if self.tls_options and settings.TCP_REQUIRE_TLS:
            features = StreamFeatures()
        else:
            features = await super(TCPStream, self).get_features()
        if self.tls_options:
            features['starttls']._set_sub_text('required',
                                               keep=settings.TCP_REQUIRE_TLS)
        return features

    async def send_init(self):
        self.stream_id = await self.generate_id()
        self.update_logger({'sid': self.stream_id})
        self.protocol_logger.info('Starting stream %s', self.stream_id)
        self.logger.debug('Starting stream')
        header = '<stream:stream %s %s %s %s %s %s>' % (
            'from="%s"' % self.host,
            'id="%s"' % self.stream_id,
            'xmlns:stream="%s"' % self.stream_ns,
            'xmlns="%s"' % self.default_ns,
            'xml:lang="%s"' % self.default_lang,
            'version="%s"' % self.version)
        self.send_raw(header)
        self.send_features()

    def abort(self):
        self.transport.loseConnection()

    def send_raw(self, data):
        data = data.encode('utf8')
        self.protocol_logger.debug('Send: %s', data)
        self.transport.write(data)

    def get_client_cert(self):
        if 'starttls' in self.features:
            return self.transport.getPeerCertificate()
        else:
            return None

    def _handle_starttls(self, xml):
        self.send(tls_stanza.Proceed())
        self.protocol_logger.debug('Starting TLS')
        self.transport.startTLS(self.tls_options)
        self.tls_options = None
        self.features.add('starttls')
        self.init_parser()

    def _auth_success(self, jid):
        self.protocol_logger.debug('Authenticated as %s', jid.bare)
        self.init_parser()

    def _session_bind(self, jid):
        self.protocol_logger.info('Bound to %s', jid.full)
