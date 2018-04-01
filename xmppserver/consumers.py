from channels.auth import AuthMiddlewareStack
from channels.exceptions import StopConsumer
from channels.consumer import AsyncConsumer
from django.conf import settings as django_settings
from django.http.request import validate_host
from django.utils.functional import cached_property
from urllib.parse import urlparse
from .xmpp.bosh import handle_bosh, disconnect_bosh
from .xmpp.websockets import handle_ws, disconnect_ws
from .conf import settings
from .utils import format_addr
import asyncio, logging

try:
    from defusedxml import ElementTree as ET
    def parse_xml(text):
        return ET.fromstring(text, forbid_dtd=True)
except ImportError:
    from xml.etree import ElementTree as ET
    def parse_xml(text):
        return ET.fromstring(text)

# try to avoid some unnecessary conversions, though perhaps
# this really belongs in some Channels middleware
class proxy_ssl_header_cache:
    @cached_property
    def header(self):
        proxy_header = django_settings.SECURE_PROXY_SSL_HEADER
        if proxy_header is not None:
            proxy_header = proxy_header[0][5:].lower().encode()
        return proxy_header
proxy_ssl = proxy_ssl_header_cache()

def get_scope_secure(scope, secure_scheme):
    proxy_header = proxy_ssl.header
    if proxy_header:
        for hdr, val in scope['headers']:
            if hdr == proxy_header:
                value = val.decode()
                return (value == secure_scheme or
                        value == django_settings.SECURE_PROXY_SSL_HEADER[1])
        return False
    return scope['scheme'] == secure_scheme

async def get_scope_user(scope):
    if not settings.ALLOW_WEBUSER_LOGIN:
        return None
    if 'user' not in scope:
        # run middleware stack on the current scope,
        # so we can find the logged-in user.
        # TODO: may need to be made more future-proof,
        # channels might make this asynchronous at some point
        AuthMiddlewareStack(lambda x: None)(scope)
    return scope['user']

def get_host(scope):
    for hdr, value in scope['headers']:
        if hdr == b'host':
            return value
    return None

def get_origin(scope):
    for hdr, value in scope['headers']:
        if hdr == b'origin':
            return value
    return None

def is_trusted_origin(origin):
    if not settings.ALLOW_WEBUSER_LOGIN:
        return False
    if origin is None:
        return True
    allowed_hosts = django_settings.ALLOWED_HOSTS
    if django_settings.DEBUG and not allowed_hosts:
        allowed_hosts = ["localhost", "127.0.0.1", "[::1]"]
    try:
        origin_host = urlparse(origin.decode()).hostname
        return validate_host(origin_host, allowed_hosts)
    except UnicodeDecodeError:
        return False

def get_addr(scope):
    # TODO: check proxy headers
    client = scope['client']
    return format_addr(client[0], client[1])

class BOSHConsumer(AsyncConsumer):
    def __init__(self, scope):
        super(BOSHConsumer, self).__init__(scope)
        self.logger = logging.LoggerAdapter(
            logging.getLogger('xmppserver.transport.bosh'),
            {'client': get_addr(scope)})
        self.parts = []
        self.stream = None
        self.rid = None
        self.answered = False
        self.http_host = get_host(scope)
        self.http_origin = get_origin(scope)
        self.loop = asyncio.get_event_loop()

    def is_secure(self):
        return get_scope_secure(self.scope, 'https')

    def is_trusted(self):
        return is_trusted_origin(self.http_origin)

    async def get_user(self):
        return await get_scope_user(self.scope)

    async def send_response(self, headers=[], body=b'', status=200):
        await self.send({
            'type': 'http.response.start',
            'status': status,
            'headers': headers,
        })
        await self.send({
            'type': 'http.response.body',
            'body': body,
        })

    async def send_data(self, data, headers):
        text = str(data)
        self.logger.debug('Send sid="%s" rid="%s": %s',
                          self.stream.sid, self.rid,
                          text)
        await self.send_response(headers,
                                 text.encode('utf8'))

    async def receive_bosh(self, event):
        self.parts.append(event['body'])
        if event.get('more_body', False):
            return
        body = b''.join(self.parts)
        self.parts = None

        self.logger.debug('Receive: %s', body)
        xml = parse_xml(body)
        await handle_bosh(self, xml)

    async def request_options(self):
        access_method = None
        for hdr, value in self.scope['headers']:
            if hdr == b'access-control-request-method':
                access_method = value
        if access_method is not None:
            # CORS preflight request
            self.logger.debug('CORS preflight request, origin %s',
                              self.http_origin)
            reply = [
                (b'vary', b'Origin'),
                (b'access-control-allow-methods', b'OPTIONS, POST'),
                (b'access-control-allow-headers', b'content-type'),
                (b'access-control-allow-origin', self.http_origin),
            ]
            if self.is_trusted():
                reply.append((b'access-control-allow-credentials', b'true'))
        else:
            # standard options
            self.logger.debug('HTTP options request')
            reply = [
                (b'allow', b'OPTIONS, POST'),
            ]
        await self.send_response(reply)

    async def invalid_request(self):
        await self.send_response(status=405)

    async def http_request(self, event):
        if self.scope['method'] == 'POST':
            await self.receive_bosh(event)
        elif self.scope['method'] == 'OPTIONS':
            await self.request_options()
        else:
            await self.invalid_request()

    async def http_disconnect(self, event):
        await disconnect_bosh(self)
        raise StopConsumer()

class WSConsumer(AsyncConsumer):
    def __init__(self, scope):
        super(WSConsumer, self).__init__(scope)
        self.logger = logging.LoggerAdapter(
            logging.getLogger('xmppserver.transport.websockets'),
            {'client': get_addr(scope)})
        self.stream = None
        self.http_host = get_host(scope)
        self.http_origin = get_origin(scope)
        self.loop = asyncio.get_event_loop()

    def is_secure(self):
        return get_scope_secure(self.scope, 'wss')

    def is_trusted(self):
        return is_trusted_origin(self.http_origin)

    async def get_user(self):
        return await get_scope_user(self.scope)

    async def close_socket(self):
        self.logger.debug('Close')
        await self.send({
            'type': 'websocket.close',
        })

    async def send_data(self, data):
        text = str(data)
        self.logger.debug('Send: %s', text)
        await self.send({
            'type': 'websocket.send',
            'text': text,
        })

    async def websocket_connect(self, event):
        subprotos = self.scope.get('subprotocols', None)
        if subprotos and 'xmpp' in subprotos:
            self.logger.debug('Connected')
            await self.send({
                'type': 'websocket.accept',
                'subprotocol': 'xmpp',
            })
        else:
            await self.close_socket()

    async def websocket_receive(self, event):
        text = event['text']
        self.logger.debug('Receive: %s', text)
        xml = parse_xml(text)
        await handle_ws(self, xml)

    async def websocket_disconnect(self, event):
        self.logger.debug('Disconnected')
        await disconnect_ws(self)
        raise StopConsumer()
