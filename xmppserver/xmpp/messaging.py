from slixmpp import Callback, StanzaPath, JID, stanza

class Messaging(object):
    def __init__(self, stream):
        self.stream = stream
        self.recv_task = None
        self.channel_name = None
        self.carbon_enabled = False

        stream.register_stanza(stanza.Message)
        stream.register_handler(
            Callback('Messaging',
                     StanzaPath('message'),
                     self._handle_message))

        stream.register_plugin('xep_0280')
        stream.register_handler(
            Callback('Carbon Enable',
                     StanzaPath('iq/carbon_enable'),
                     self._handle_carbon_enable))
        stream.register_handler(
            Callback('Carbon Disable',
                     StanzaPath('iq/carbon_disable'),
                     self._handle_carbon_disable))

    def _handle_message(self, msg):
        msg['from'] = self.stream.boundjid
        self.stream.loop.create_task(self._ipc_send_message(msg))

    def _handle_carbon_enable(self, iq):
        self.carbon_enabled = True
        iq.reply().send()

    def _handle_carbon_disable(self, iq):
        self.carbon_enabled = False
        iq.reply().send()

    def carbon_wrap(self, xml, carbon_type):
        msg = stanza.Message(self.stream)
        msg['from'] = self.stream.boundjid.bare
        msg['to'] = self.stream.boundjid.full
        msg['type'] = xml.attrib.get('type', '')
        msg[carbon_type] = xml
        return msg

    def relay(self, origin, ifrom, xml, private=False):
        target = JID(xml.attrib['to'])
        if target.resource != '' and \
           target.resource != self.stream.boundjid.resource:
            # not meant for this stream
            if self.carbon_enabled and not private:
                # but if carbons are enabled...
                self.carbon_wrap(xml, 'carbon_received').send()
            return
        self.stream.send_element(xml)

    async def ipc_recv_message(self, origin, ifrom, xml):
        self.relay(origin, ifrom, xml)

    async def ipc_recv_private(self, origin, ifrom, xml):
        self.relay(origin, ifrom, xml, private=True)

    async def ipc_recv_carbon(self, origin, ifrom, xml):
        if self.carbon_enabled:
            if ifrom == self.stream.boundjid.full:
                return
            self.carbon_wrap(xml, 'carbon_sent').send()
        return

    async def _ipc_send_message(self, msg):
        target = msg['to']
        if target.user == '':
            # the message might be addressed to a nickname;
            # I haven't found any reference for that actually
            # being allowed, so for now, treat that as a
            # message for a username on the local server.
            target.user = target.domain
            target.domain = self.stream.host
            msg['to'] = target
        if not self.stream.is_local(target.domain):
            # can't handle remote domains yet
            reply = msg.reply()
            reply['error']['condition'] = 'remote-server-not-found'
            reply.send()
            return
        private = False
        for stanza in msg.iterables:
            if stanza.name == 'private':
                private = True
        if private:
            del msg['carbon_private']
            await self.stream.ipc_send('messaging.private',
                                       target,
                                       msg.xml)
        else:
            await self.stream.ipc_send('messaging.message',
                                       target,
                                       msg.xml)
            await self.stream.ipc_send('messaging.carbon',
                                       self.stream.boundjid,
                                       msg.xml)
