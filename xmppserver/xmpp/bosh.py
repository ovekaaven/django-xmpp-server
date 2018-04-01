from random import randint
from slixmpp import BaseXMPP
from slixmpp.xmlstream import tostring
from .stream import min_version, StreamElement, Stream
from ..conf import settings

MAX_VER = '1.8'
NS_XBOSH = 'urn:xmpp:xbosh'

# streams handled by this process
streams = {}

def get_local_stream(id):
    return streams.get(id, None)

def set_local_stream(id, session):
    streams[id] = session

def clear_local_stream(id):
    del streams[id]

xbosh_restart = '{%s}restart' % NS_XBOSH
xbosh_restartlogic = '{%s}restartlogic' % NS_XBOSH
xbosh_version = '{%s}version' % NS_XBOSH

class BOSHBody(StreamElement):
    name = 'body'
    namespace = 'http://jabber.org/protocol/httpbind'
    interfaces = {'from', 'to', 'sid', 'version',
                  'type', 'condition'}
    types = {'terminate', None}

    def get_version(self):
        return self.xml.attrib[xbosh_version]
    def set_version(self, value):
        self.xml.attrib[xbosh_version] = value

def build_headers(content=b'text/xml; charset=utf-8',
                  origin=None, trust=False):
    headers = [
        (b'content-type', content)
    ]
    if origin is not None:
        headers.append((b'access-control-allow-origin', origin))
        if trust:
            headers.append((b'access-control-allow-credentials', 'true'))
    return headers

def get_empty_body():
    return tostring(BOSHBody().xml, top_level=True)

def get_recoverable_body():
    body = BOSHBody()
    body['type'] = 'error'
    return tostring(body.xml, top_level=True)

class BOSHStream(Stream):
    empty_body = get_empty_body()
    recoverable_body = get_recoverable_body()

    def __init__(self):
        super(BOSHStream, self).__init__()
        self.update_logger({'transport': 'BOSH'})
        self.consumers = {}
        self.requests = {}
        self.replies = {}
        self.content_type = b'text/xml; charset=utf-8'
        self.http_host = None
        self.http_origin = None
        self.trust_origin = False
        self.sid = None
        self.rid_in = None
        self.rid_out = None
        self.rid_ack = None
        self.use_ack = False
        self.current_body = None
        self.bosh_started = False
        self.bosh_ver = None
        self.bosh_wait = None
        self.bosh_inactivity = settings.BOSH_MAX_INACTIVITY
        self.inactivity_handle = None
        self.dead = False
        self.restarting = False
        self.frozen = 0
        self.add_event_handler('auth_success',
                               self._auth_success)

    async def prebind(self, username, host, resource=None):
        self.logger.debug('Prebinding BOSH, username %s', username)
        if not self.host:
            self.host = host
        if username is not None:
            self.boundjid.user = username
        else:
            self.boundjid.user = await self.auth.generate_anonymous_user()
        self.boundjid.domain = self.host
        if resource is not None:
            self.boundjid.resource = resource
        else:
            self.boundjid.resource = await self.auth.generate_resource_id()
        self.sid = self.generate_id()
        self.update_logger({'sid': self.sid,
                            'jid': self.boundjid.full})

        self.version = '1.0'
        self.rid_in = randint(0,0xffffffff)
        self.rid_out = self.rid_in
        self.rid_ack = self.rid_out
        set_local_stream(self.sid, self)
        self.set_session_timeout()

        self.logger.info('BOSH session prebound for JID %s', self.boundjid.full)

        # prebind may be done from a different event loop than the
        # actual BOSH requests, so reset the cached loop property
        # (perhaps we should make sure it's not cached at all?)
        #self._loop = None

        # TODO: verify that the session timeout installed above
        # actually works despite the different event loops;
        # perhaps we should make an ASGI consumer for prebinding?

        data = {'jid': self.boundjid.full,
                'sid': self.sid,
                'rid': self.rid}
        return data

    def start_stream_handler(self, xml):
        self.logger.debug('Starting stream')
        # we're completely overriding Stream.start_stream_handler,
        # so we don't want to call that, just the BaseXMPP version
        BaseXMPP.start_stream_handler(self, xml)
        attrs = xml.attrib
        if 'content' in attrs:
            self.content_type = attrs.get('content').encode('utf8')
        self.rid_in = int(attrs.get('rid', '1'))
        self.rid_out = self.rid_in
        self.rid_ack = self.rid_out
        self.use_ack = 'ack' in attrs
        self.bosh_started = True
        self.bosh_ver = min_version(attrs.get('ver', '1.0'), MAX_VER)
        # TODO: polling-only clients
        self.bosh_wait = min(max(int(attrs.get('wait', '60')),
                                 settings.BOSH_MIN_WAIT),
                             settings.BOSH_MAX_WAIT)
        self.bosh_hold = min(int(attrs.get('hold', '1')),
                             settings.BOSH_MAX_HOLD)
        self.bosh_requests = self.bosh_hold + 1
        if not self.host and 'to' in attrs:
            self.host = attrs['to']
        if 'from' in attrs:
            self.requested_jid.full = attrs['from']
        self.version = '1.0'
        self.boundjid.domain = self.host
        if self.bosh_wait:
            for consumer in self.consumers.values():
                self.set_consumer_timeout(consumer)
        self.rid_in += 1
        self.loop.create_task(self.send_init(xml))

    def connection_lost(self, reason=None):
        if self.dead:
            return
        self.dead = True
        if self.inactivity_handle:
            self.inactivity_handle.cancel()
            self.inactivity_handle = None
        if self.sid is not None:
            clear_local_stream(self.sid)
        super(BOSHStream, self).connection_lost(reason)

    def set_consumer_timeout(self, consumer):
        consumer.wait_handle = self.loop.call_later(self.bosh_wait, self.expire_request, consumer)

    def set_session_timeout(self):
        self.inactivity_handle = self.loop.call_later(self.bosh_inactivity, self.inactive)

    def add_consumer(self, consumer, xml):
        rid = int(xml.attrib.get('rid', '1'))
        if rid in self.replies:
            self.send_to_consumer(consumer, self.replies[rid])
            return

        consumer.rid = rid
        if rid in self.consumers:
            old_consumer = self.consumers[rid]
            self.remove_request(old_consumer)
            old_consumer.rid = None
            self.send_to_consumer(old_consumer, self.recoverable_body)

        if self.inactivity_handle is not None:
            self.inactivity_handle.cancel()
            self.inactivity_handle = None
        if self.bosh_wait:
            self.set_consumer_timeout(consumer)
        self.consumers[rid] = consumer

        if not self.bosh_started:
            return self.start_stream_handler(xml)

        if self.use_ack:
            if 'ack' in xml.attrib:
                ack = int(xml.attrib.get('ack'))
            else:
                ack = rid - 1
        elif 'ack' in xml.attrib:
            # prebinding must assume client won't send ack,
            # but we should adapt in case it does
            self.use_ack = True
            ack = int(xml.attrib.get('ack'))
        else:
            ack = rid - self.bosh_requests
        if ack >= self.rid_out: # sanity check
            ack = self.rid_out - 1
        while self.rid_ack <= ack:
            self.replies.pop(self.rid_ack)
            self.rid_ack += 1

        if (rid < self.rid_in or
            rid >= self.rid_in + self.bosh_requests):
            self.terminate('item-not-found')
            return

        self.send_freeze()
        self.requests[rid] = xml
        while self.rid_in in self.requests:
            xml = self.requests.pop(self.rid_in)
            self.rid_in += 1
            self.process_request(xml)
        # Since process_request might start tasks, we should
        # use call_soon in order to give those tasks a chance
        # to run before we send off any response, so that we
        # can pack as many stanzas as possible.
        self.loop.call_soon(self.send_thaw)

    def add_consumer_threadsafe(self, consumer, xml):
        if consumer.loop == self.loop:
            self.add_consumer(consumer, xml)
            return
        self.loop.call_soon_threadsafe(self.add_consumer,
                                       consumer, xml)

    def remove_consumer(self, consumer):
        if not consumer.answered:
            self.remove_request(consumer)

    def remove_consumer_threadsafe(self, consumer):
        if consumer.loop == self.loop:
            self.remove_consumer(consumer)
            return
        self.loop.call_soon_threadsafe(self.remove_consumer,
                                       consumer)

    def del_consumer(self, consumer):
        self.consumers.pop(consumer.rid)
        if not self.consumers:
            self.set_session_timeout()

    def inactive(self):
        self.connection_lost()

    def process_request(self, xml):
        if xbosh_restart in xml.attrib:
            # If a stream restart is requested, XEP-0206 says to
            # ignore the rest of the request, but XEP-0305 changes
            # that to processing the restart after authentication.
            self.restarting = True
        for child in xml:
            self.handle_stanza(child)
        if 'type' in xml.attrib:
            type = xml.attrib['type']
            if type == 'terminate':
                self.restarting = False
                self.terminate()

    def remove_request(self, consumer):
        if self.bosh_wait:
            consumer.wait_handle.cancel()
        self.del_consumer(consumer)

    def _send_cb(self, consumer, data, headers):
        consumer.loop.create_task(consumer.send_data(data, headers))

    def send_to_consumer(self, consumer, data):
        headers = self.http_headers
        consumer.answered = True
        if consumer.rid is not None:
            self.replies[consumer.rid] = data
        if consumer.loop == self.loop:
            self._send_cb(consumer, data, headers)
            return
        consumer.loop.call_soon_threadsafe(self._send_cb,
                                           consumer,
                                           data,
                                           headers)

    def expire_request(self, consumer):
        self.del_consumer(consumer)
        self.send_to_consumer(consumer, self.empty_body)

    def flush_requests(self):
        while self.consumers:
            rid, consumer = self.consumers.popitem()
            if self.bosh_wait:
                consumer.wait_handle.cancel()
            self.send_to_consumer(consumer, self.empty_body)

    def send_body_to(self, consumer):
        if self.bosh_wait:
            consumer.wait_handle.cancel()
        xml = self.current_body.xml
        self.current_body = None
        ack = self.rid_in - 1
        if ack != consumer.rid:
            xml.attrib['ack'] = str(ack)
        data = tostring(xml, top_level=True)
        self.send_to_consumer(consumer, data)

    def send_body(self):
        consumer = self.consumers.pop(self.rid_out, None)
        if not consumer:
            return
        self.rid_out += 1
        self.send_body_to(consumer)

    def send(self, data):
        if not self.current_body:
            self.current_body = BOSHBody()
        self.current_body.append(data)
        if self.frozen == 0:
            self.send_body()

    send_element = send

    def abort(self):
        self.terminate('remote-connection-failed')

    def send_error(self, error=None):
        if error:
            self.terminate('remote-stream-error', error)
        else:
            self.abort()

    def send_freeze(self):
        self.frozen += 1

    def send_thaw(self):
        self.frozen -= 1
        if self.frozen != 0:
            return
        if self.restarting:
            # standard restart (XEP-0206)
            self.send_features()
            self.restarting = False
            return
        if self.current_body:
            self.send_body()
        # try to enforce hold limit
        while (len(self.consumers) > self.bosh_hold and
               self.rid_out in self.consumers):
            self.current_body = BOSHBody()
            self.send_body()

    def _auth_success(self, jid):
        if self.restarting:
            # pipelined restart (XEP-0305)
            self.send_features()
            self.restarting = False

    def terminate(self, condition=None, data=None):
        if not self.current_body:
            self.current_body = BOSHBody()
        self.current_body['type'] = 'terminate'
        if condition:
            self.current_body['condition'] = condition
        if data:
            self.current_body.append(data)
        if not self.consumers:
            return
        consumer = self.consumers.pop(self.rid_out, None)
        if not consumer:
            # if we've lost rid_out, just pick
            # some arbitrary consumer for now,
            # though perhaps we're supposed to
            # pick oldest or something
            rid, consumer = self.consumers.popitem()
        self.send_body_to(consumer)
        self.flush_requests()
        self.connection_lost()

    def send_raw(self, data):
        # send_raw shouldn't be used with BOSH
        raise NotImplementedError()

    async def send_init(self, xml=None):
        # finish initialization of non-prebound sessions
        if self.sid is None:
            self.sid = await self.generate_id()
            self.update_logger({'sid': self.sid})
            if not self.consumers:
                # nobody to send the sid to
                self.connection_lost()
                return
            set_local_stream(self.sid, self)

        # prepare response
        self.logger.debug('Starting stream')
        self.http_headers = build_headers(content=self.content_type,
                                          origin=self.http_origin,
                                          trust=self.trust_origin)
        self.send_freeze()
        if not self.current_body:
            body = BOSHBody()
            attrs = body.xml.attrib
            attrs['from'] = self.host
            attrs['sid'] = self.sid
            attrs[xbosh_restartlogic] = 'true'
            attrs[xbosh_version] = self.version
            attrs['ver'] = self.bosh_ver
            attrs['wait'] = str(self.bosh_wait)
            attrs['hold'] = str(self.bosh_hold)
            attrs['requests'] = str(self.bosh_requests)
            attrs['inactivity'] = str(self.bosh_inactivity)
            attrs['ack'] = str(self.rid_in - 1)
            self.current_body = body
        if self.boundjid.user != '':
            await self.auth.prebound()
        self.send(await self.get_features())
        if xml:
            self.process_request(xml)
        self.send_thaw()


async def prebind_bosh_stream(web_user, username, domain, resource=None,
                              host=None, origin=None):
    stream = BOSHStream()
    stream.http_host = host
    stream.http_origin = origin
    # no need to set stream.trust_origin, the user has already authenticated
    # to the prebind view, so the BOSH URL won't need the credentials
    stream.web_user = web_user
    return await stream.prebind(username, domain, resource)

async def handle_bosh(consumer, xml):
    if 'sid' not in xml.attrib:
        stream = BOSHStream()
        stream.http_host = consumer.http_host
        stream.http_origin = consumer.http_origin
        stream.trust_origin = consumer.is_trusted()
        if stream.trust_origin:
            stream.web_user = await consumer.get_user()
    else:
        stream = get_local_stream(xml.attrib['sid'])
        if not stream:
            # stream is gone
            reply = BOSHBody()
            reply['type'] = 'terminate'
            reply['condition'] = 'remote-connection-failed'
            await consumer.send_data(tostring(reply.xml, top_level=True),
                                     build_headers(origin=consumer.http_origin,
                                                   trust=consumer.is_trusted()))
            return
        if stream.http_host != consumer.http_host:
            # We're going to consider an unexpected host fishy,
            # perhaps there's a man-in-the-middle attack or something.
            await consumer.send_response(status=403)
            return
        elif not stream.bosh_started and not consumer.http_origin:
            # On the first BOSH request, if it seems the browser
            # don't think it's necessary to send us origin headers,
            # don't expect them for future requests either.
            stream.http_origin = None
        elif stream.http_origin != consumer.http_origin:
            # Possible stream hijacking attempt. We'll just tell
            # the browser what origin we accept, it'll do the rest.
            await consumer.send_response(stream.http_headers)
            return
    consumer.stream = stream
    stream.add_consumer_threadsafe(consumer, xml)

async def disconnect_bosh(consumer):
    if consumer.stream:
        consumer.stream.remove_consumer_threadsafe(consumer)
