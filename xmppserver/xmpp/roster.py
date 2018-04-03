from slixmpp import Callback, JID
from slixmpp.exceptions import XMPPError
from slixmpp.stanza import Iq, roster as roster_stanza
from slixmpp.xmlstream import register_stanza_plugin
from .matcher import ServerStanzaPath

register_stanza_plugin(Iq, roster_stanza.Roster)

class Roster(object):
    def __init__(self, stream):
        self.stream = stream
        self.interested = False
        self.cached = None
        self.delay_pushes = 0
        self.delayed_pushes = []

        stream.register_plugin('feature_preapproval')
        # TBD: should we try to support roster versioning?
        stream.register_handler(
            Callback('Roster',
                     ServerStanzaPath('iq/roster'),
                     self._handle_roster))

    def _handle_roster(self, iq):
        iq['from'] = self.stream.boundjid
        type = iq['type']
        if type == 'get':
            self.interested = True
            self.stream.loop.create_task(self._get_roster(iq))
        elif type == 'set':
            self.stream.loop.create_task(self._set_roster(iq))
        else:
            iq.unhandled()

    def user_deleted(self):
        self.stream.loop.create_task(self._delete_roster())

    async def send_push(self, user, jid, values,
                        checked=True):
        # called when a subscription is being changed
        iq = Iq(self.stream)
        iq['type'] = 'set'
        iq['roster'].set_items({jid.bare: values})
        if checked:
            type = 'roster.push'
        else:
            type = 'roster.push_unchecked'
        await self.stream.ipc_send(type,
                                   user,
                                   iq.xml)

    async def _relay_push(self, xml, checked):
        if checked:
            # Though the IPC push messages do give us notification that
            # the database has changed, messages are not guaranteed to
            # arrive in the same order that the database was updated.
            # So just in case, we should get up-to-date information from
            # the database before relaying any pushes to the user.
            iq = Iq(self.stream, xml)
            contacts = iq['roster'].get_items()
            for jid, values in contacts.items():
                values = await self.stream.roster_hook.get_contact(self.stream.boundjid,
                                                                   jid)
                if values is None:
                    values = {'subscription': 'remove'}
                contacts[jid] = values
            iq['roster'].set_items(contacts)
            xml = iq.xml
        self.stream.send_element(xml)

    async def ipc_recv_push(self, origin, ifrom, xml,
                            checked=True):
        if not self.interested:
            return
        xml.attrib['to'] = self.stream.boundjid.full
        if self.delay_pushes:
            self.delayed_pushes.append((xml, checked))
        else:
            await self._relay_push(xml, checked)

    async def ipc_recv_push_unchecked(self, origin, ifrom, xml):
        await self.ipc_recv_push(origin, ifrom, xml,
                                 checked=False)

    async def _get_roster(self, iq):
        try:
            roster = await self.stream.roster_hook.get_contacts(self.stream.boundjid)
            if roster is None:
                raise XMPPError('item-not-found')
        except Exception as e:
            iq.exception(e)
            return

        # When clients connect, they usually get the roster first,
        # then set initial presence, which also needs the roster.
        # We could cache the roster here so that the initial presence
        # wouldn't have to retrieve it again. However, that is a risky
        # thing to do; the client might never send presence, meaning
        # we'd be wasting memory, or the client might wait a while,
        # meaning our cached roster might be outdated (unless we keep
        # it up-to-date, which is possible but not implemented).
        # So for now, we won't cache the roster, but maybe we can
        # implement a safe way to do this in the future.
        #if not self.stream.presence.available:
        #    self.cached = roster

        reply = iq.reply()
        items = reply['roster']
        for jid, values in roster:
            item = roster_stanza.RosterItem()
            item.values = values
            item.set_jid(jid)
            items.append(item)
        reply.send()

    async def _set_roster(self, iq):
        try:
            self.delay_pushes += 1
            items = {}
            try:
                contacts = iq['roster'].get_items()
                if len(contacts) != 1:
                    raise XMPPError('bad-request')
                for jid, values in contacts.items():
                    if jid.bare == self.stream.boundjid.bare:
                        raise XMPPError('not-allowed')
                    if values.get('subscription', 'none') != 'remove':
                        if jid.user == '':
                            # the request might be addressed to a nickname;
                            # I haven't found any reference for that actually
                            # being allowed, so for now, treat that as a
                            # query for a username on the local server
                            # (while also telling the client to remove the
                            # original request, just in case).
                            items[jid] = {'subscription': 'remove'}
                            jid = JID(jid)
                            jid.user = jid.domain
                            jid.domain = self.stream.host
                        items[jid] = await self._update_contact(jid, values)
                    else:
                        items[jid] = await self._remove_contact(jid)
            except Exception as e:
                iq.exception(e)
                return
            iq.reply().send()
            # push to other resources of the same user
            del iq['from']
            iq['roster'].set_items(items)
            await self.stream.ipc_send('roster.push',
                                       self.stream.boundjid,
                                       iq.xml)
        finally:
            self.delay_pushes -= 1
            if self.delay_pushes == 0:
                pushes = self.delayed_pushes
                self.delayed_pushes = []
                for xml, checked in pushes:
                    await self._relay_push(xml, checked)

    async def _delete_roster(self):
        roster = await self.stream.roster_hook.get_contacts(self.stream.boundjid)
        for jid, values in roster:
            await self._remove_contact(jid)

    async def _update_contact(self, jid, values):
        if self.stream.kicked:
            raise XMPPError('forbidden')
        new_values = await self.stream.roster_hook.update_contact(self.stream.boundjid,
                                                                  jid, values)
        if new_values is None:
            # If the roster hook won't add the contact,
            # tell the client that it's removed
            new_values = {'subscription': 'remove'}
        return new_values

    async def _remove_contact(self, jid):
        values = await self.stream.roster_hook.get_contact(self.stream.boundjid,
                                                           jid)
        if values is None:
            raise XMPPError('item-not-found')
        await self.stream.presence.removing_contact(jid, values)

        # If another resource re-subscribes or something after we call
        # get_contact and before we call remove_contact, then the
        # removal may fail (return False). But since we're delaying
        # roster pushes from other resources while doing this,
        # we can just ignore the failure and pretend that the contact
        # was immediately re-added by the other resource.
        await self.stream.roster_hook.remove_contact(self.stream.boundjid,
                                                     jid)

        return {'subscription': 'remove'}
