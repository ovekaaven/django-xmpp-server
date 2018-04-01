from channels.layers import get_channel_layer
from slixmpp import BaseXMPP, Callback, JID
from slixmpp.api import APIRegistry
from slixmpp.plugins import PluginManager
from slixmpp.stanza import Iq, StreamError
from slixmpp.xmlstream import (ElementBase, StanzaBase, XMLStream,
                               tostring)
from .matcher import RemoteStanzaPath
from .features import Features
from .auth import Auth
from .disco import Disco
from .ping import Ping
from .roster import Roster
from .presence import Presence
from .messaging import Messaging
from .registration import Registration
from ..conf import settings
from ..hooks import get_hook
import asyncio, uuid
import logging

def min_version(a, b):
    v_a = [int(x) for x in a.split('.')]
    v_b = [int(x) for x in b.split('.')]
    v_min = min(v_a, v_b)
    return ".".join([str(x) for x in v_min])

class StreamElement(StanzaBase):
    name = 'stream'
    namespace = 'jabber:client'
    # attributes defined in RFC 6120, section 4.7.
    # (xml:lang is handled by ElementBase)
    interfaces = set(['from', 'to', 'id', 'version'])

class Stream(BaseXMPP):
    ping_keepalives = False
    whitespace_keepalives = False

    def __init__(self):
        # BaseXMPP does way too much crap in its __init__,
        # we'll have to skip it and do stuff ourselves
        XMLStream.__init__(self)
        self.default_ns = 'jabber:client'
        self.stream_ns = 'http://etherx.jabber.org/streams'
        self.namespace_map[self.stream_ns] = 'stream'
        self.requested_jid = JID()
        self.boundjid = JID()
        self.session_bind_event = asyncio.Event()
        self.plugin = PluginManager(self)
        self.plugin_config = {}
        self.is_component = True
        self.use_message_ids = False
        self.use_presence_ids = False
        self.api = APIRegistry(self)
        self.register_stanza(Iq)
        self.register_stanza(StreamError)
        self.authenticated = True # keep slixmpp's xep_0078 from doing stupid stuff

        # And now for our own initialization...
        self.logger_extra = {'sid': '', 'jid': ''}
        self.logger = logging.LoggerAdapter(
            logging.getLogger('xmppserver.stream'),
            self.logger_extra)
        self.ipc_logger = logging.LoggerAdapter(
            logging.getLogger('xmppserver.ipc'),
            self.logger_extra)
        self.web_user = None
        self.bound_user = None
        self.host = settings.DOMAIN
        self.kicked = False
        self._auth_hook = None
        self._roster_hook = None
        self._session_hook = None
        self.version = None
        self.default_lang = 'en'
        self.recv_task = None
        self.channel_name = None
        self.group_name = None
        self.channel_layer = get_channel_layer('xmppserver')

        self.register_plugin('xep_0086') # legacy error codes

        self.features = Features(self)
        self.disco = Disco(self)
        self.auth = Auth(self)
        self.registration = Registration(self)
        self.ping = Ping(self)
        # we only need the following components
        # after the client has authenticated.
        self.roster = None
        self.presence = None
        self.messaging = None

        self.register_handler(
            Callback('Remote Iq',
                     RemoteStanzaPath('iq'),
                     self._handle_iq))

        self.logger.debug('Creating stream')

    @property
    def auth_hook(self):
        if self._auth_hook is None:
            self._auth_hook = get_hook('auth')()
        return self._auth_hook

    @property
    def roster_hook(self):
        if self._roster_hook is None:
            self._roster_hook = get_hook('roster')()
        return self._roster_hook

    @property
    def session_hook(self):
        if self._session_hook is None:
            self._session_hook = get_hook('session')()
        return self._session_hook

    def update_logger(self, extra):
        self.logger_extra.update(extra)

    def start_stream_handler(self, xml):
        BaseXMPP.start_stream_handler(self, xml)
        if not self.host and 'to' in xml.attrib:
            self.host = xml.attrib['to']
        if 'from' in xml.attrib:
            self.requested_jid.full = xml.attrib['from']
        self.version = '1.0'
        self.boundjid.domain = self.host
        self.loop.create_task(self.send_init())

    async def send_init(self):
        pass

    def prepare_features(self):
        self.roster = Roster(self)
        self.presence = Presence(self)
        self.messaging = Messaging(self)

    async def bind(self):
        self.channel_name = await self.channel_layer.new_channel()
        self.group_name = self.group_for_user(self.boundjid)
        self.recv_task = self.loop.create_task(self._receive_task())
        await self.roster_hook.bind(self)

    async def unbind(self):
        self.logger.debug('Destroying stream')
        if self._roster_hook:
            await self._roster_hook.unbind(self)
        if self._session_hook:
            await self._session_hook.unbind(self)
        if self._auth_hook:
            await self._auth_hook.unbind(self)
        await self._cleanup_task()

    def connection_lost(self, reason=None):
        self.event('disconnected', reason)
        if self.recv_task:
            self.recv_task.cancel()
        self.loop.create_task(self.unbind())

    def get_client_cert(self):
        return None

    async def generate_id(self):
        return str(uuid.uuid4())

    async def get_features(self):
        if 'mechanisms' not in self.features:
            # not authenticated
            return await self.auth.get_features()
        else:
            return await self.features.get_features()

    def send_features(self):
        self.loop.create_task(self._feature_task())

    async def _feature_task(self):
        self.send(await self.get_features())

    def handle_stanza(self, xml):
        self._spawn_event(xml)

    def abort(self):
        pass

    def send_freeze(self):
        pass

    def send_thaw(self):
        pass

    def send(self, data):
        if isinstance(data, ElementBase):
            self.send_element(data.xml)
        else:
            self.send_raw(data)

    def send_element(self, xml):
        self.send_raw(tostring(xml, xmlns=self.default_ns,
                               stream=self, top_level=True))

    def send_error(self, error=None):
        if error:
            self.send(error)
        self.abort()

    def _start_keepalive(self, event):
        # workaround: slixmpp forgot to actually check whitespace_keepalive
        if self.whitespace_keepalive:
            super(Stream, self)._start_keepalive(event)

    def is_local(self, domain):
        return domain == self.host

    def exception(self, exception):
        self.logger.exception('Unhandled stream exception')

    # User Deletion

    def user_deleted(self):
        self.kicked = True
        self.ipc_send_soon('deleted', self.boundjid, None)
        self.roster.user_deleted()

    async def ipc_recv_deleted(self, origin, ifrom, xml):
        self.kicked = True
        error = StreamError()
        error['condition'] = 'not-authorized'
        self.send_error(error)

    # Remote Iq

    def _handle_iq(self, iq):
        iq['from'] = self.boundjid
        self.loop.create_task(self._ipc_send_iq(iq))

    async def ipc_recv_iq(self, origin, ifrom, xml):
        target = JID(xml.attrib['to'])
        if target.resource != self.boundjid.resource:
            return
        self.send_element(xml)

    async def _ipc_send_iq(self, iq):
        target = iq['to']
        if not self.is_local(target.domain):
            # can't handle other domains yet
            reply = iq.reply()
            reply['error']['condition'] = 'remote-server-not-found'
            reply.send()
            return
        await self.ipc_send('iq',
                            target,
                            iq.xml)

    # IPC over Channel Layers

    @staticmethod
    def group_for_user(jid):
        return 'xmpp.user.' + jid.user

    async def _receive_task(self):
        await self.channel_layer.group_add(self.group_name,
                                           self.channel_name)
        while True:
            msg = await self.channel_layer.receive(self.channel_name)
            await self._ipc_received(msg)

    async def _cleanup_task(self):
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name,
                                                   self.channel_name)
            self.group_name = None
        self.channel_name = None

    def ipc_send_soon(self, type, target, xml):
        self.loop.create_task(self.ipc_send(type, target, xml))

    async def ipc_send(self, type, target, xml):
        group_name = self.group_for_user(target)
        if self.ipc_logger.isEnabledFor(logging.DEBUG):
            self.ipc_logger.debug("IPC-Send type %s from %s [%s] to %s: %s",
                                  type, self.boundjid, self.channel_name,
                                  target.bare, tostring(xml))
        await self.channel_layer.group_send(
            group_name, {
                'type': type,
                'origin': self.channel_name,
                'from': self.boundjid.full,
                'xml': xml,
            })

    async def ipc_reply(self, type, channel, xml):
        if self.ipc_logger.isEnabledFor(logging.DEBUG):
            self.ipc_logger.debug("IPC-Reply type %s from %s to [%s]: %s",
                                  type, self.boundjid, channel,
                                  tostring(xml))
        await self.channel_layer.send(
            channel, {
                'type': type,
                'origin': self.channel_name,
                'from': self.boundjid.full,
                'xml': xml,
            })

    async def _ipc_received(self, msg):
        type = msg['type']
        xml = msg['xml']
        origin = msg['origin']
        ifrom = msg['from']
        if self.ipc_logger.isEnabledFor(logging.DEBUG):
            self.ipc_logger.debug("IPC-Receive type %s from %s [%s]: %s",
                                  type, ifrom, origin,
                                  tostring(xml))
        try:
            attrs = type.split('.')
            target = self
            for attr in attrs[:-1]:
                target = getattr(target, attr)
            target = getattr(target, 'ipc_recv_' + attrs[-1])
            await target(origin, ifrom, xml)
        except Exception as e:
            self.exception(e)
