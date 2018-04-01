from slixmpp import Callback
from slixmpp.exceptions import XMPPError
from slixmpp.plugins.xep_0077 import stanza as register_stanza
from .matcher import ServerStanzaPath
from ..conf import settings

class Registration(object):
    def __init__(self, stream):
        self.stream = stream

        stream.register_plugin('xep_0077')
        stream['xep_0030'].add_feature(register_stanza.Register.namespace)

        stream.register_handler(
            Callback('Registration',
                     ServerStanzaPath('iq/register'),
                     self._handle_register))

    def _handle_register(self, iq):
        type = iq['type']
        if type == 'get':
            self.stream.loop.create_task(self._get_register(iq))
        elif type == 'set':
            self.stream.loop.create_task(self._set_register(iq))
        else:
            iq.unhandled()

    async def _get_register(self, iq):
        reply = iq.reply()
        fields = reply['register']
        if settings.ALLOW_REGISTRATION:
            # TODO: field customization.
            if 'mechanisms' in self.stream.features:
                # already authenticated
                fields.set_registered(True)
                fields['username'] = self.stream.boundjid.user
                fields.add_field('password')
            else:
                fields.add_field('username')
                fields.add_field('password')
        else:
            url = settings.REGISTRATION_URL
            if url is None:
                url = 'http://' + self.stream.host
            fields['instructions'] = 'To register, visit %s' % url
            fields['oob']['url'] = url
        reply.send()

    async def _set_register(self, iq):
        if not settings.ALLOW_REGISTRATION:
            reply = iq.reply()
            reply['error']['condition'] = 'not-allowed'
            reply.send()
            return
        fields = iq['register']

        try:
            if fields.get_remove():
                # delete registration
                if 'mechanisms' not in self.stream.features:
                    raise XMPPError('forbidden')
                username = self.stream.boundjid.user
                await self.stream.roster_hook.delete_user()
                self.stream.user_deleted()
            elif 'mechanisms' in self.stream.features:
                # update registration
                username = fields['username']
                if username != self.stream.boundjid.user:
                    raise XMPPError('bad-request')
                password = fields['password']
                if password != '':
                    await self.stream.roster_hook.change_password(password)
            else:
                # create registration
                # TODO: try to avoid registration spam
                username = fields['username']
                password = fields['password']
                if username == '' or password == '':
                    raise XMPPError('not-acceptable')
                if not await self.stream.roster_hook.create_user(username, password):
                    raise XMPPError('conflict')
        except Exception as e:
            iq.exception(e)
            return
        iq.reply().send()
