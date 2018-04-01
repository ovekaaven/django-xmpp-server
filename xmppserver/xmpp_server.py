from twisted.internet import reactor, ssl
from twisted.internet.protocol import Protocol, ServerFactory
from twisted.internet.endpoints import TCP6ServerEndpoint
from .xmpp.tcp import TCPStream
from .conf import settings
from .utils import format_addr
import logging

class XMPPServer(Protocol):
    def __init__(self, factory):
        self.stream = None
        self.factory = factory
        self.logger = factory.logger
        self.client = None

    def connectionMade(self):
        try:
            peer = self.transport.getPeer()
            self.client = format_addr(peer.host, peer.port)
            self.logger = logging.LoggerAdapter(self.factory.logger,
                                                {'client': self.client})
            self.logger.info('Connected')
            self.stream = TCPStream(self)
        except:
            self.logger.exception('Error opening stream')
            raise

    def dataReceived(self, data):
        if self.stream:
            try:
                self.logger.debug('Receive: %s', data)
                self.stream.data_received(data)
            except:
                self.logger.exception('Error processing data')
                raise

    def connectionLost(self, reason=None):
        if self.stream:
            try:
                self.logger.info('Disconnected')
                self.stream.connection_lost()
            except:
                self.logger.exception('Error closing stream')
                raise
            self.stream = None

class XMPPServerFactory(ServerFactory):
    def __init__(self, logger):
        super(XMPPServerFactory, self).__init__()
        self.logger = logger
        authorities = []
        if settings.TLS_CACERT_PATHS:
            for path in settings.TLS_CACERT_PATHS:
                pub_key = open(path).read()
                authorities.append(ssl.Certificate.loadPEM(pub_key))
        if settings.TLS_CERT_PATH and settings.TLS_PRIV_KEY_PATH:
            try:
                priv_key = open(settings.TLS_PRIV_KEY_PATH).read()
                pub_key = open(settings.TLS_CERT_PATH).read()
                priv_cert = ssl.PrivateCertificate.loadPEM(priv_key + pub_key)
            except IOError:
                self.logger.exception("Couldn't load XMPP server certificate, TLS disabled")
                self.options = None
            else:
                self.options = priv_cert.options(*authorities)
        else:
            self.logger.warning('XMPP server certificate not configured, TLS disabled')
            self.options = None
        if self.options is None and settings.TCP_REQUIRE_TLS:
            raise Exception("XMPP_TCP_REQUIRE_TLS is True, but XMPP server certificate not available")

    def buildProtocol(self, addr):
        return XMPPServer(self)

def start_xmpp_server():
    logger = logging.getLogger('xmppserver.transport.tcp')
    logger.info('Starting XMPP server', extra={'client': 'SERVER'})
    c_endpoint = TCP6ServerEndpoint(reactor, settings.TCP_CLIENT_PORT)
    c_endpoint.listen(XMPPServerFactory(logger))
    # should be no need to run the reactor, the ASGI host (Daphne) already does
