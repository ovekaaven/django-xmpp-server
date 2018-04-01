from channels.db import database_sync_to_async
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth import get_user_model
from .base import BaseRosterHook

class DefaultRosterHook(BaseRosterHook):

    # Since I don't want to define any models in the main xmppserver
    # module, the default roster hook isn't doing much. For proper
    # roster support, the xmppserver.rosterdb app should be added.

    async def bind(self, stream):
        self.auth_hook = stream.auth_hook

    async def unbind(self, stream):
        self.auth_hook = None


class EveryoneRosterHook(DefaultRosterHook):

    # Roster hook that may be suitable for a helpdesk or community app.

    def get_username(self, contact):
        return self.auth_hook.get_webuser_username(contact)

    def filter_user(self, user, contact):
        if self.get_username(contact) == user.username:
            return False
        return contact.is_active

    def get_roster_values(self, contact):
        fullname = contact.get_full_name()
        if not fullname:
            fullname = self.get_username(contact)
        return {'name': fullname, 'subscription': 'both'}

    @database_sync_to_async
    def get_contacts(self, user):
        contacts = []
        for contact in get_user_model().objects.all():
            if not self.filter_user(user, contact):
                continue
            jid = "%s@%s" % (self.get_username(contact), user.domain)
            contacts.append((jid, self.get_roster_values(contact)))
        return contacts

    @database_sync_to_async
    def get_contact(self, user, jid):
        try:
            contact = get_user_model().objects.get_by_natural_key(jid.username)
        except ObjectDoesNotExist:
            return None
        if not self.filter_user(user, contact):
            return None
        return self.get_roster_values(contact)

class StaffRosterHook(EveryoneRosterHook):

    # Roster hook that may be suitable for a helpdesk app.

    def filter_user(self, user, contact):
        if not super(StaffRosterHook, self).filter_user(user, contact):
            return False
        return getattr(contact, 'is_staff', None)
