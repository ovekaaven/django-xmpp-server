from slixmpp import Callback, JID, stanza
from slixmpp.plugins.xep_0030 import stanza as disco_stanza
from slixmpp.xmlstream import register_stanza_plugin
from .matcher import LocalStanzaPath

class Disco(object):
    def __init__(self, stream):
        self.stream = stream
        self.disco_features = []

        # slixmpp's xep_0030 does too much crap we don't need,
        # so patch ourselves in instead.
        stream.plugin._enabled.add('xep_0030')
        stream.plugin._plugins['xep_0030'] = self

        register_stanza_plugin(stanza.Iq, disco_stanza.DiscoInfo)
        register_stanza_plugin(stanza.Iq, disco_stanza.DiscoItems)

        stream.register_handler(
            Callback('Disco Info',
                     LocalStanzaPath('iq/disco_info'),
                     self._handle_disco_info))
        stream.register_handler(
            Callback('Disco Items',
                     LocalStanzaPath('iq/disco_items'),
                     self._handle_disco_items))

    def _end(self):
        pass

    def add_feature(self, feature):
        self.disco_features.append(feature)

    def del_feature(self, feature):
        self.disco_features.remove(feature)

    async def _allow_access(self, jid):
        if jid.user == self.stream.boundjid.user:
            return True
        values = self.stream.roster_hook.get_contact(jid)
        if values is None:
            return False
        sub = values.get('subscription', 'none')
        return sub == 'both' or sub == 'to'

    def _handle_disco_info(self, iq):
        target = iq['to']
        if target.user == '':
            # return server features
            disco = iq['disco_info']
            reply = iq.reply(clear=False)
            if disco['node']:
                reply['error']['condition'] = 'item-not-found'
                reply.send()
                return
            info = reply['disco_info']
            info.add_identity('server', 'im')
            info.add_feature(disco_stanza.DiscoInfo.namespace)
            info.add_feature(disco_stanza.DiscoItems.namespace)
            for feature in self.disco_features:
                info.add_feature(feature)
            reply.send()
        else:
            self.stream.loop.create_task(self._handle_user_info(iq))

    async def _handle_user_info(self, iq):
        target = iq['to']
        disco = iq['disco_info']
        reply = iq.reply(clear=False)
        if not await self._allow_access(target):
            reply['error']['condition'] = 'service-unavailable'
            reply.send()
            return
        if disco['node']:
            reply['error']['condition'] = 'item-not-found'
            reply.send()
            return
        info = reply['disco_info']
        info.add_identity('account', 'registered')
        info.add_feature(disco_stanza.DiscoInfo.namespace)
        info.add_feature(disco_stanza.DiscoItems.namespace)
        reply.send()

    def _handle_disco_items(self, iq):
        target = iq['to']
        if target.user == '':
            # return server components
            reply = iq.reply()
            items = reply['disco_items']
            # components not implemented yet
            reply.send()
        else:
            self.stream.loop.create_task(self._handle_user_items(iq))

    async def _handle_user_items(self, iq):
        target = iq['to']
        disco = iq['disco_items']
        reply = iq.reply(clear=False)
        if not await self._allow_access(target):
            reply.send()
            return
        if disco['node']:
            reply.send()
            return
        result = await self.stream.session_hook.get_all_resources(target.user)
        if result:
            items = reply['disco_items']
            for resource, priority in result:
                jid = JID(target)
                jid.resource = resource
                items.add_item(jid)
        reply.send()
