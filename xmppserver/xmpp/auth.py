from asyncio import iscoroutine, wrap_future, InvalidStateError
from concurrent.futures import Future # threadpool-compatible futures
from slixmpp import Callback, StanzaPath
from slixmpp.exceptions import XMPPError
from slixmpp.features.feature_mechanisms import stanza as auth_stanza
from slixmpp.plugins import xep_0078
from slixmpp.stanza import StreamFeatures
from .mechanisms import get_sasl_available, get_sasl_by_name, LegacyAuth
from ..conf import settings
import uuid

# workaround: slixmpp's Failure may reference condition_ns without defining it
auth_stanza.Failure.condition_ns = auth_stanza.Failure.namespace

class Auth(object):
    def __init__(self, stream):
        self.stream = stream
        self.auth_task = None
        self.bind_func = None
        self.response_fut = None
        self.responses = None
        stream.credentials = {} # feature_mechanisms need this
        stream.register_plugin('feature_mechanisms')
        stream.register_handler(
            Callback('Auth',
                     StanzaPath('auth'),
                     self._handle_auth))
        stream.register_handler(
            Callback('Auth Response',
                     StanzaPath('response'),
                     self._handle_response))
        stream.register_handler(
            Callback('Auth Abort',
                     StanzaPath('abort'),
                     self._handle_abort))
        if LegacyAuth.available(self):
            # need to explicitly specify module here since xep_0078
            # is purposefully unavailable by default
            stream.register_plugin('xep_0078', module=xep_0078)
            stream.register_handler(
                Callback('LegacyAuth',
                         StanzaPath('iq/auth'),
                         self._handle_legacy_auth))

        stream.register_plugin('feature_bind')
        stream.register_handler(
            Callback('Bind',
                     StanzaPath('iq/bind'),
                     self._handle_bind))

        stream.register_plugin('feature_session')
        stream.register_handler(
            Callback('Session',
                     StanzaPath('iq/session'),
                     self._handle_session))

        stream.add_event_handler('disconnected',
                                 self._disconnected)

    async def get_features(self):
        features = StreamFeatures()
        available = await get_sasl_available(self)
        features['mechanisms'] = [m.name for m in available]
        if await LegacyAuth.available(self):
            features._get_plugin('auth')
        features._get_plugin('register')
        return features

    async def generate_resource_id(self):
        return uuid.uuid4().hex

    async def generate_anonymous_user(self):
        return uuid.uuid4().hex

    async def check_password(self, username, password):
        if not password:
            # client didn't supply a password, maybe they
            # want web session authentication
            web_user = self.stream.web_user
            if web_user:
                return await self.stream.auth_hook.check_webuser(self.stream,
                                                                 web_user, username)
            # if web authentication isn't available,
            # we won't allow passwordless logins
        elif password.startswith('//jid/'):
            # seems to be a session token
            return await self.stream.auth_hook.check_token(self.stream,
                                                           username, password[6:])
        elif settings.ALLOW_PLAIN_PASSWORD:
            # ordinary password
            return await self.stream.auth_hook.check_password(self.stream,
                                                              username, password)
        return False

    async def prebound(self):
        if 'mechanisms' not in self.stream.features:
            await self._auth_success()
            await self._bind_attempt()
            await self._bind_success()

    def _disconnected(self, reason):
        self._abort_auth()

    async def _auth_success(self):
        jid = self.stream.boundjid.bare
        self.stream.update_logger({'jid': jid})
        self.stream.logger.info('Authenticated as %s', jid)
        self.stream.features.add('mechanisms')
        self.stream.prepare_features()
        await self.stream.auth_hook.bind(self.stream)
        self.stream.event('auth_success', self.stream.boundjid)

    async def _async_challenge(self, data):
        challenge = auth_stanza.Challenge()
        challenge['value'] = data
        self.stream.send(challenge)
        while not self.responses:
            self.stream.send_thaw()
            await wrap_future(self.response_fut)
            self.response_fut = Future()
            self.stream.send_freeze()
        return self.responses.pop(0)

    async def _auth_task(self, auth, process):
        try:
            ret = process(auth)
            if iscoroutine(ret):
                await ret
        except Exception as e:
            self.stream.logger.info('Authentication failure')
            reply = auth_stanza.Failure()
            if isinstance(e, XMPPError):
                reply['condition'] = e.condition
            elif isinstance(e, UnicodeDecodeError):
                reply['condition'] = 'malformed-request'
            else:
                reply['condition'] = 'temporary-auth-failure'
                self.stream.logger.exception('Unhandled authentication exception')
            self.stream.send(reply)
            self.stream.send_thaw()
        else:
            # TODO: what if self.responses is non-empty
            # (i.e., we've received too many responses?)
            self.responses = None
            self.response_fut = None
            self.stream.send(auth_stanza.Success())
            await self._auth_success()
            if self.bind_func:
                await self.bind_func
            self.stream.send_thaw()
            self.auth_task = None

    def _handle_auth(self, auth):
        # TODO: handle unexpected auth
        if 'mechanisms' in self.stream.features or self.auth_task:
            # already authenticated, or in progress
            # TODO: send error?
            return
        mech = get_sasl_by_name(auth['mechanism'])
        if not mech or not mech.available(self):
            reply = auth_stanza.Failure()
            reply['condition'] = 'invalid-mechanism'
            self.stream.send(reply)
            return
        self.stream.send_freeze()
        task = self._auth_task(auth, mech(self).process)
        self.auth_task = self.stream.loop.create_task(task)
        self.responses = []
        self.response_fut = Future()

    def _handle_response(self, response):
        # TODO: handle unexpected response
        if not self.response_fut:
            # TODO: send error?
            return
        self.responses.append(response['value'])
        # wake up the thread, in case it's waiting for this
        try:
            self.response_fut.set_result()
        except InvalidStateError:
            # guess it wasn't waiting... it'll get to the
            # queued response on its own, eventually
            pass

    def _abort_auth(self):
        if self.auth_task:
            self.bind_func = None
            # auth_task and response_fut run in different threads,
            # so have to cancel both to avoid stuck threads
            self.auth_task.cancel()
            if self.response_fut:
                self.response_fut.cancel()
                self.responses = None
                self.response_fut = None
            self.stream.send_thaw()
            self.auth_task = None

    def _handle_abort(self, abort):
        self._abort_auth()
        reply = auth_stanza.Failure()
        reply['condition'] = 'aborted'
        self.stream.send(reply)

    async def _bind_attempt(self):
        # If there's a resource conflict, force a new resource ID.
        while not await self.stream.session_hook.bind(self.stream):
            resource = await self.generate_resource_id()
            self.stream.boundjid.resource = resource

    async def _bind_success(self):
        jid = self.stream.boundjid.full
        self.stream.update_logger({'jid': jid})
        self.stream.logger.info('Bound to %s', jid)
        self.stream.session_bind_event.set()
        await self.stream.bind()
        self.stream.event('session_bind', self.stream.boundjid)
        self.stream.event('session_start')

    async def _bind_task(self, bind):
        self.bind_func = None
        resource = bind['bind']['resource']
        if resource == '':
            resource = await self.generate_resource_id()
        self.stream.boundjid.resource = resource
        try:
            await self._bind_attempt()
        except Exception as e:
            bind.exception(e)
            return
        reply = bind.reply()
        reply['bind']['jid'] = self.stream.boundjid.full
        reply.send()
        await self._bind_success()

    def _handle_bind(self, bind):
        if self.stream.session_bind_event.is_set() or \
           self.bind_func:
            # already bound
            # TODO: send error?
            return
        if 'mechanisms' not in self.stream.features and \
            not self.auth_task:
            # not authenticated yet
            # TODO: send error?
            return
        # If authentication is not complete yet, then this must
        # be a pipelined request, and should be held until after
        # authentication. Otherwise, schedule it now.
        self.bind_func = self._bind_task(bind)
        if not self.auth_task:
            self.stream.loop.create_task(self.bind_func)

    def _handle_session(self, session):
        # RFC 3921 session creation is obsolete,
        # so return success but otherwise do nothing
        session.reply().send()

    async def _legacy_auth_get(self, iq):
        reply = iq.reply(clear=False)
        auth = reply['auth']
        auth.clear()
        auth._set_sub_text('username', keep=True)
        if not settings.ALLOW_WEBUSER_LOGIN:
            auth._set_sub_text('password', keep=True)
        auth._set_sub_text('resource', keep=True)
        reply.send()

    async def _legacy_auth_task(self, iq, process):
        try:
            ret = process(iq)
            if iscoroutine(ret):
                await ret
            await self._bind_attempt()
        except Exception as e:
            self.stream.logger.info('Authentication failure')
            reply = iq.reply()
            reply['type'] = 'error'
            if isinstance(e, XMPPError):
                reply['error']['condition'] = e.condition
            else:
                reply['error']['condition'] = 'internal-server-error'
                self.stream.logger.exception('Unhandled authentication exception')
            reply.send()
        else:
            iq.reply().send()
            await self._auth_success()
            await self._bind_success()
            self.auth_task = None

    def _handle_legacy_auth(self, iq): # XEP-0078
        if 'mechanisms' in self.stream.features or self.auth_task:
            # already authenticated, or in progress
            # TODO: send error?
            return
        type = iq['type']
        auth = iq['auth']
        if type == 'get':
            task = self._legacy_auth_get(auth)
            self.stream.loop.create_task(task)
        elif type == 'set':
            process = LegacyAuth(self).process
            task = self._legacy_auth_task(auth, process)
            self.auth_task = self.stream.loop.create_task(task)
        else:
            iq.unhandled()
