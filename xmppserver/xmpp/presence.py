from slixmpp import Callback, StanzaPath, JID, stanza
from slixmpp.exceptions import XMPPError
from slixmpp.xmlstream import tostring
from xml.etree import ElementTree as ET

def build_presence_xml(jid, type='available'):
    msg = stanza.Presence()
    msg['type'] = type
    msg['from'] = jid
    return msg.xml

def build_presence_dbxml(jid, presence, type='available'):
    if presence:
        return ET.fromstring(presence)
    else:
        return build_presence_xml(jid, type)

class Presence(object):
    to_types = {'to', 'both'}
    from_types = {'from', 'both'}
    unsubscribe_map = {'both': 'from', 'to': 'none'}
    unsubscribed_map = {'both': 'to', 'from': 'none'}

    def __init__(self, stream):
        self.stream = stream
        self.available = False
        self.last_presence = None
        self.directed_presence = set()

        stream.register_stanza(stanza.Presence)
        stream.register_handler(
            Callback('Presence',
                     StanzaPath('presence'),
                     self._handle_presence))

        stream.add_event_handler('disconnected',
                                 self._disconnected)

    async def removing_contact(self, jid, values):
        # called when a contact is being removed from the roster
        sub = values.get('subscription', 'none')
        if sub in self.to_types or 'ask' in values:
            msg = self.stream.Presence()
            msg['type'] = 'unsubscribe'
            msg['to'] = jid
            await self._outbound_unsubscribe(msg, push=False)
        if sub in self.from_types:
            msg = self.stream.Presence()
            msg['type'] = 'unsubscribed'
            msg['to'] = jid
            await self._outbound_unsubscribed(msg, push=False)

    def _handle_presence(self, msg):
        type = msg._get_attr('type')
        if type == '':
            if msg['to'] == '':
                self.stream.loop.create_task(self._set_presence(msg))
            else:
                self.stream.loop.create_task(self._directed_presence(msg))
        elif type == 'unavailable':
            if msg['to'] == '':
                self.stream.loop.create_task(self._set_absence(msg))
            else:
                self.stream.loop.create_task(self._directed_absence(msg))
        elif type == 'subscribe':
            self.stream.loop.create_task(self._outbound_subscribe(msg))
        elif type == 'subscribed':
            self.stream.loop.create_task(self._outbound_subscribed(msg))
        elif type == 'unsubscribe':
            self.stream.loop.create_task(self._outbound_unsubscribe(msg))
        elif type == 'unsubscribed':
            self.stream.loop.create_task(self._outbound_unsubscribed(msg))
        elif type == 'probe':
            self.stream.loop.create_task(self._send_probe(msg))
        else:
            reply = msg.reply()
            reply['error']['condition'] = 'bad-request'
            reply.send()

    def _disconnected(self, reason):
        self.stream.loop.create_task(self._set_absence())

    def relay(self, origin, ifrom, xml):
        if not self.available:
            return
        xml.attrib['to'] = self.stream.boundjid.bare
        self.stream.send_element(xml)

    async def ipc_recv_available(self, origin, ifrom, xml):
        self.relay(origin, ifrom, xml)

    async def ipc_recv_unavailable(self, origin, ifrom, xml):
        self.directed_presence.discard(xml.attrib['from'])
        self.relay(origin, ifrom, xml)

    async def ipc_recv_probe(self, origin, ifrom, xml):
        if not self.available:
            return
        if ifrom == self.stream.boundjid.full:
            # should ignore probes from ourselves.
            return
        await self.stream.ipc_reply('presence.available',
                                    origin,
                                    self.last_presence.xml)

    async def ipc_recv_subscription(self, origin, ifrom, xml):
        self.relay(origin, ifrom, xml)

    async def ipc_recv_subscribed(self, origin, ifrom, xml):
        if not self.available:
            return
        await self.stream.ipc_send('presence.available',
                                   JID(xml.attrib['to']),
                                   self.last_presence.xml)

    async def ipc_recv_unsubscribed(self, origin, ifrom, xml):
        if not self.available:
            return
        await self._send_unavailable(self.stream.boundjid,
                                     JID(xml.attrib['to']))

    async def _send_unavailable(self, user, contact, xml=None):
        if xml is None:
            msg = self.stream.Presence()
            msg['type'] = 'unavailable'
            msg['from'] = user.full
        await self.stream.ipc_send('presence.unavailable',
                                   contact,
                                   msg.xml)

    async def _set_presence(self, msg):
        msg['from'] = self.stream.boundjid.full
        initial = not self.available
        self.last_presence = msg
        self.available = True
        await self.stream.session_hook.set_presence(msg['priority'],
                                                    tostring(msg.xml))
        # clients usually get the roster before becoming
        # available, so use cached roster if possible
        roster = self.stream.roster.cached
        if roster is None:
            roster = await self.stream.roster_hook.get_contacts(self.stream.boundjid)
        await self._broadcast_presence(msg, roster, initial)
        if initial:
            await self._remind_pending()

    async def _broadcast_presence(self, msg, roster, initial=False):
        await self.stream.ipc_send('presence.available',
                                   self.stream.boundjid,
                                   msg.xml)
        if initial:
            probe = self.stream.Presence()
            probe['type'] = 'probe'
            probe['from'] = self.stream.boundjid.bare
        else:
            probe = None
        local_contacts = {self.stream.boundjid.username: [self.stream.boundjid]}
        if roster:
            for jid, values in roster:
                contact = JID(jid)
                sub = values.get('subscription', 'none')
                if sub in self.from_types:
                    await self.stream.ipc_send('presence.available',
                                               contact,
                                               msg.xml)
                if probe and sub in self.to_types:
                    if self.stream.is_local(contact.domain):
                        local_contacts.setdefault(contact.username, []).append(contact)
        if probe:
            await self._probe_local(local_contacts, probe.xml)

    async def _set_absence(self, msg=None):
        if msg is None:
            msg = self.stream.Presence()
            msg['type'] = 'unavailable'
        msg['from'] = self.stream.boundjid.full
        if self.available:
            self.last_presence = msg
            self.available = False
            await self.stream.session_hook.set_presence(None, None)
            roster = await self.stream.roster_hook.get_contacts(self.stream.boundjid)
            await self._broadcast_absence(msg, roster)
        # terminate any directed presence
        for jid in self.directed_presence:
            await self.stream.ipc_send('presence.unavailable',
                                       JID(jid),
                                       msg.xml)
        self.directed_presence.clear()

    async def _broadcast_absence(self, msg, roster):
        await self.stream.ipc_send('presence.unavailable',
                                   self.stream.boundjid,
                                   msg.xml)
        if roster:
            for jid, values in roster:
                contact = JID(jid)
                sub = values.get('subscription', 'none')
                if sub in self.from_types:
                    await self.stream.ipc_send('presence.unavailable',
                                               contact,
                                               msg.xml)

    async def _directed_presence(self, msg):
        msg['from'] = self.stream.boundjid.full
        target = msg['to']
        self.directed_presence.add(target.full)
        await self.stream.ipc_send('presence.available',
                                   target,
                                   msg.xml)

    async def _directed_absence(self, msg):
        msg['from'] = self.stream.boundjid.full
        target = msg['to']
        self.directed_presence.discard(target.full)
        await self.stream.ipc_send('presence.unavailable',
                                   target,
                                   msg.xml)

    async def _probe_local(self, contacts, xml):
        def send(contact, resource, presence):
            jid = JID(contact)
            jid.resource = resource
            if jid == self.stream.boundjid:
                return
            msg_xml = build_presence_dbxml(jid, presence)
            msg_xml.attrib['to'] = self.stream.boundjid.bare
            self.stream.send_element(msg_xml)

        presences = (await self.stream.session_hook.
                     get_all_roster_presences(contacts.keys()))
        if presences is None:
            # apparently, fast-path is not available,
            # do it the slow way then
            for username, jids in contacts.items():
                presences = (await self.stream.session_hook.
                             get_all_presences(username))
                if presences is None:
                    # no session database, try IPC broadcast
                    for contact in jids:
                        await self.stream.ipc_send('presence.probe',
                                                   contact,
                                                   xml)
                else:
                    for resource, priority, presence in presences:
                        for contact in jids:
                            send(contact, resource, presence)
        else:
            # yay, we can do it the fast way
            for username, resource, priority, presence in presences:
                for contact in contacts[username]:
                    send(contact, resource, presence)

    async def _send_probe(self, msg):
        msg['from'] = self.stream.boundjid.bare
        await self.stream.ipc_send('presence.probe',
                                   msg['to'],
                                   msg.xml)

    async def _remind_pending(self):
        # nag user about Pending-In contacts
        pending = await self.stream.roster_hook.get_pending(self.stream.boundjid)
        if pending is None:
            return
        for jid, presence in pending:
            xml = build_presence_dbxml(jid, presence, 'subscribe')
            self.stream.send_element(xml)

    async def _remote_server(self, msg):
        reply = msg.reply()
        reply['error']['condition'] = 'remote-server-not-found'
        reply.send()
        return False

    async def _handle_subscribed(self, msg, user, contact, values):
        if self.stream.is_local(contact.domain):
            await self._inbound_subscribed(msg.xml, contact, user)
        elif not await self._remote_server(msg):
            return
        if values is not None:
            await self.stream.roster.send_push(user, contact, values)
            presences = (await self.stream.session_hook.
                         get_all_presences(user.username))
            if presences is None:
                # no session database, try IPC broadcast
                await self.stream.ipc_send('presence.subscribed',
                                           user,
                                           msg.xml)
            else:
                for resource, priority, presence in presences:
                    jid = JID(contact)
                    jid.resource = resource
                    msg_xml = build_presence_dbxml(jid, presence)
                    await self.stream.ipc_send('presence.available',
                                               contact,
                                               msg_xml)

    async def _handle_unsubscribe(self, xml, user, contact, values,
                                  push=True):
        values.pop('ask', None)
        sub = values.get('subscription', 'none')
        if sub in self.to_types:
            values['subscription'] = self.unsubscribe_map.get(sub, sub)
        if push:
            await self.stream.roster.send_push(user, contact, values)

    async def _handle_unsubscribed(self, xml, user, contact, values,
                                   preapproved=False, push=True):
        sub = values.get('subscription', 'none')
        subscribed = sub in self.from_types
        if subscribed:
            values['subscription'] = self.unsubscribed_map.get(sub, sub)
        if push and (subscribed or preapproved):
            await self.stream.roster.send_push(user, contact, values)
        if not subscribed:
            return False
        resources = await (self.stream.session_hook.
                           get_all_resources(user.username))
        if resources is None:
            # no session database, try IPC broadcast
            await self.stream.ipc_send('presence.unsubscribed',
                                       user,
                                       xml)
        else:
            for resource, priority in resources:
                jid = JID(user)
                jid.resource = resource
                await self._send_unavailable(jid, contact)
        return True

    async def _outbound_subscribe(self, msg):
        try:
            if self.stream.kicked:
                raise XMPPError('forbidden')
            user = self.stream.boundjid
            contact = msg['to']
            msg['from'] = user.bare
            if contact.resource:
                # 'to' field must be bare
                contact.resource = ''
                msg['to'] = contact
            if contact.user == '':
                # the request might be addressed to a nickname;
                # I haven't found any reference for that actually
                # being allowed, so for now, treat that as a
                # query for a username on the local server.
                contact.user = contact.domain
                contact.domain = self.stream.host
                msg['to'] = contact
            stanza_out = tostring(msg.xml)
            values = (await self.stream.roster_hook.
                      outbound_subscribe(user, contact,
                                         stanza_out))
            # Even if we're already subscribed, the RFC doesn't say not to
            # forward the stanza (maybe in case the remote server didn't receive
            # a previous subscribe?), so we're only going to suppress the
            # roster push (after all, the roster wouldn't have changed).
            if self.stream.is_local(contact.domain):
                if not await self.stream.auth_hook.valid_contact(contact.user):
                    reply = msg.reply()
                    reply['error']['condition'] = 'item-not-found'
                    reply.send()
                    return
                await self._inbound_subscribe(msg.xml, contact, user,
                                              stanza_out)
            elif not self._remote_server(msg):
                return
            if values is not None:
                await self.stream.roster.send_push(user, contact, values)
        except Exception as e:
            msg.exception(e)
            return

    async def _outbound_subscribed(self, msg):
        try:
            if self.stream.kicked:
                raise XMPPError('forbidden')
            user = self.stream.boundjid
            contact = msg['to']
            msg['from'] = user.bare
            values = (await self.stream.roster_hook.
                      outbound_subscribed(user, contact))
            await self._handle_subscribed(msg, user, contact, values)
        except Exception as e:
            msg.exception(e)
            return

    async def _outbound_unsubscribe(self, msg, push=True):
        try:
            user = self.stream.boundjid
            contact = msg['to']
            msg['from'] = user.bare
            values = (await self.stream.roster_hook.
                      outbound_unsubscribe(user, contact))
            if values is not None:
                await self._handle_unsubscribe(msg.xml, user, contact, values,
                                               push)
            if self.stream.is_local(contact.domain):
                await self._inbound_unsubscribe(msg.xml, contact, user)
            elif not self._remote_server(msg):
                return
        except Exception as e:
            msg.exception(e)
            return

    async def _outbound_unsubscribed(self, msg, push=True):
        try:
            user = self.stream.boundjid
            contact = msg['to']
            msg['from'] = user.bare
            values = (await self.stream.roster_hook.
                      outbound_unsubscribed(user, contact))
            if values is None:
                return # already unsubscribed
            preapproved = values.pop('approved', None)
            sub = await self._handle_unsubscribed(msg.xml, user, contact, values,
                                                  preapproved, push)
            if preapproved and not sub:
                # We should forward only if we were in the subscribed or
                # Pending-In state, but the latter isn't explicit in the
                # values returned by the hook, just implicit by the absence
                # of any from-subscription or pre-approval. So we'll suppress
                # forwarding only if we removed a pre-approval (the extra
                # "not subscribed" check is unnecessary, but can't hurt).
                return
            if self.stream.is_local(contact.domain):
                await self._inbound_unsubscribed(msg.xml, contact, user)
            elif not self._remote_server(msg):
                return
        except Exception as e:
            msg.exception(e)
            return

    async def _inbound_subscribe(self, xml, user, contact, stanza_in):
        values = (await self.stream.roster_hook.
                  inbound_subscribe(user, contact, stanza_in))
        if values is False:
            return # already pending
        if values is True:
            # Seems the request should be delivered to the client.
            # Note: the RFC says that if the server was able to
            # deliver the request to an available resource, then
            # it MAY acknowledge it to the sender by returning an
            # 'unavailable' presence stanza from the user's bare JID.
            # I'm unsure of whether this would constitute a presence
            # leak, so I'm going to ignore it for now.
            await self.stream.ipc_send('presence.subscription',
                                       user,
                                       xml)
            return
        msg = self.stream.Presence()
        msg['type'] = 'subscribed'
        msg['from'] = user
        await self._handle_subscribed(msg, user, contact, values)

    async def _inbound_subscribed(self, xml, user, contact):
        values = (await self.stream.roster_hook.
                  inbound_subscribed(user, contact))
        if values is None:
            return
        await self.stream.ipc_send('presence.subscription',
                                   user,
                                   xml)
        await self.stream.roster.send_push(user, contact, values)

    async def _inbound_unsubscribe(self, xml, user, contact):
        values = (await self.stream.roster_hook.
                  inbound_unsubscribe(user, contact))
        if values is None:
            return
        if await self._handle_unsubscribed(xml, user, contact, values):
            await self.stream.ipc_send('presence.subscription',
                                       user,
                                       xml)

    async def _inbound_unsubscribed(self, xml, user, contact):
        values = (await self.stream.roster_hook.
                  inbound_unsubscribed(user, contact))
        if values is None:
            return
        await self._handle_unsubscribe(xml, user, contact, values)
        await self.stream.ipc_send('presence.subscription',
                                   user,
                                   xml)
