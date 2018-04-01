from channels.db import database_sync_to_async
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction, IntegrityError, OperationalError
from django.db.models.functions import Now
from ..hooks import DefaultRosterHook
from .models import XMPPContact
import logging

logger = logging.getLogger('xmppserver.rosterdb')

def atomic_update(func):
    def wrapper(*args, **kwargs):
        while True:
            try:
                with transaction.atomic():
                    return func(*args, **kwargs)
            except IntegrityError:
                # If this transaction needed to create a contact, some
                # other thread may have created the contact between
                # the retrieve and the save, resulting in either a
                # serialization failure or an integrity error (where
                # the latter would be because of the model's
                # unique_together constraint). With any isolation level
                # below 'serializable', such as Django's default of
                # 'read committed', we should get the integrity error.
                # (If anyone is running at the serializable level
                # (with a database other than SQLite), I haven't looked
                # into handling that yet, so suggestions are welcome.)
                logger.info('Retrying contact update due to integrity error')
                continue
            except OperationalError as e:
                # If we're using SQLite, we might instead get a
                # 'database is locked' error, which, for short-lived
                # transactions such as these, we can think of as a
                # kind of serialization failure, caused by Django's
                # reckless use of deferred transactions.
                # Maybe someone will patch Django someday...
                if e.args[0] == 'database is locked':
                    logger.error('Retrying contact update due to database lock')
                    continue
                raise
            except ObjectDoesNotExist:
                # Most hook methods should just return None if the
                # contact doesn't exist, so we'll have a convenience
                # handler here.
                return None
    return wrapper

class RosterHook(DefaultRosterHook):

    def set_roster_values(self, contact, values):
        contact.name = values.get('name', '')
        groups = values.get('groups', [])

        # Store groups in database as a semicolon-separated string.
        # (Existing semicolons in the group names are escaped with colons.
        # which of course means colons must also be escaped.)
        # Doing this is more efficient than using foreign keys,
        # and also much easier, given that the client uploads the
        # whole list every time it updates a roster entry.
        contact.groups = ';'.join([group.
                                   replace(':', ':.').
                                   replace(';', ':,')
                                   for group in groups])

    def get_roster_values(self, contact, omit_none=False):
        values = {}
        if contact.name:
            values['name'] = contact.name
        if contact.subscribed_to:
            if contact.subscribed_from:
                values['subscription'] = 'both'
            else:
                values['subscription'] = 'to'
        else:
            if contact.subscribed_from:
                values['subscription'] = 'from'
            elif not omit_none:
                values['subscription'] = 'none'
        if contact.preapproved:
            values['approved'] = 'true'
        if contact.pending_out:
            values['ask'] = 'subscribe'
        if contact.groups:
            groups = [group.
                      replace(':,', ';').
                      replace(':.', ':')
                      for group in contact.groups.split(';')]
            values['groups'] = groups
        return values

    def retrieve_for_update(self, user, jid):
        return (XMPPContact.objects.
                select_for_update().
                get(username=user.user,
                             contact=jid.bare))

    def retrieve_or_create(self, user, jid):
        try:
            return self.retrieve_for_update(user, jid)
        except ObjectDoesNotExist:
            logger.debug('Creating contact')
            return XMPPContact(username=user.user,
                               contact=jid.bare)

    @database_sync_to_async
    def get_contacts(self, user):
        logger.debug('Retrieve: roster %s all data', user.user)
        query = (XMPPContact.objects.
                 filter(username=user.user,
                        in_roster=True))
        return [(contact.contact, self.get_roster_values(contact, True))
                for contact in query]

    @database_sync_to_async
    def get_contact(self, user, jid):
        logger.debug('Retrieve: roster %s contact %s data',
                     user,user, jid.bare)
        try:
            contact = (XMPPContact.objects.
                       get(username=user.user,
                           contact=jid.bare,
                           in_roster=True))
        except ObjectDoesNotExist:
            return None
        else:
            return self.get_roster_values(contact)

    @database_sync_to_async
    @atomic_update
    def update_contact(self, user, jid, values):
        logger.debug('Update: roster %s contact %s data',
                     user.user, jid.bare)
        contact = self.retrieve_or_create(user, jid)
        contact.in_roster = True
        self.set_roster_values(contact, values)
        values = self.get_roster_values(contact)
        contact.save()
        return values

    @database_sync_to_async
    @atomic_update
    def remove_contact(self, user, jid):
        logger.debug('Update: roster %s contact %s remove',
                     user.user, jid.bare)
        contact = self.retrieve_for_update(user, jid)
        if not contact.in_roster:
            return None
        if (contact.subscribed_from or
            contact.subscribed_to or
            contact.pending_out):
            return False
        if contact.pending_in:
            contact.in_roster = False
            contact.preapproved = False
            contact.name = ''
            contact.groups = ''
            contact.save()
            return True
        contact.delete()
        return True

    @database_sync_to_async
    def get_pending(self, user):
        logger.debug('Retrieve: user %s all pending', user.user)
        return list(XMPPContact.objects.filter(username=user.user,
                                               pending_in__isnull=False).
                    values_list('contact', 'stanza_in'))

    @database_sync_to_async
    def is_pending(self, user, jid):
        logger.debug('Retrieve: user %s contact %s pending',
                     user,user, jid.bare)
        return bool(XMPPContact.objects.filter(username=user.user,
                                               contact=jid.bare).
                    values_list('pending_in', flat=True).
                    first())

    @database_sync_to_async
    @atomic_update
    def inbound_subscribe(self, user, jid, stanza=''):
        logger.debug('Update: user %s contact %s inbound-subscribe',
                     user.user, jid.bare)
        contact = self.retrieve_or_create(user, jid)
        if contact.subscribed_from:
            return None
        if contact.preapproved:
            contact.subscribed_from = True
            contact.preapproved = False
            values = self.get_roster_values(contact)
            contact.save()
            return values
        was_pending = contact.pending_in
        contact.pending_in = Now()
        contact.stanza_in = stanza
        contact.save()
        return not was_pending

    @database_sync_to_async
    @atomic_update
    def inbound_subscribed(self, user, jid):
        logger.debug('Update: user %s contact %s inbound-subscribed',
                     user.user, jid.bare)
        contact = self.retrieve_for_update(user, jid)
        if not contact.pending_out:
            return None
        contact.subscribed_to = True
        contact.pending_out = None
        contact.stanza_out = ''
        values = self.get_roster_values(contact)
        contact.save()
        return values

    @database_sync_to_async
    @atomic_update
    def inbound_unsubscribe(self, user, jid):
        logger.debug('Update: user %s contact %s inbound-unsubscribe',
                     user.user, jid.bare)
        contact = self.retrieve_for_update(user, jid)
        if not contact.in_roster:
            contact.delete()
            return {}
        if not (contact.subscribed_from or
                contact.pending_in):
            return None
        values = self.get_roster_values(contact)
        contact.subscribed_from = False
        contact.pending_in = None
        contact.stanza_in = ''
        contact.save()
        return values

    @database_sync_to_async
    @atomic_update
    def inbound_unsubscribed(self, user, jid):
        logger.debug('Update: user %s contact %s inbound-unsubscribed',
                     user.user, jid.bare)
        contact = self.retrieve_for_update(user, jid)
        if not (contact.subscribed_to or
                contact.pending_out):
            return None
        values = self.get_roster_values(contact)
        contact.subscribed_to = False
        contact.pending_out = None
        contact.stanza_out = ''
        contact.save()
        return values

    @database_sync_to_async
    @atomic_update
    def outbound_subscribe(self, user, jid, stanza=''):
        logger.debug('Update: user %s contact %s outbound-subscribe',
                     user.user, jid.bare)
        contact = self.retrieve_or_create(user, jid)
        if (contact.subscribed_to or
            contact.pending_out):
            return None
        contact.in_roster = True
        contact.pending_out = Now()
        contact.stanza_out = stanza
        values = self.get_roster_values(contact)
        contact.save()
        return values

    @database_sync_to_async
    @atomic_update
    def outbound_subscribed(self, user, jid):
        logger.debug('Update: user %s contact %s outbound-subscribed',
                     user.user, jid.bare)
        contact = self.retrieve_or_create(user, jid)
        contact.in_roster = True
        if contact.pending_in:
            contact.subscribed_from = True
            contact.pending_in = None
            contact.stanza_in = ''
        else:
            if (contact.subscribed_to or
                contact.preapproved):
                return None
            contact.preapproved = True
        values = self.get_roster_values(contact)
        contact.save()
        return values

    @database_sync_to_async
    @atomic_update
    def outbound_unsubscribe(self, user, jid):
        logger.debug('Update: user %s contact %s outbound-unsubscribe',
                     user.user, jid.bare)
        contact = self.retrieve_for_update(user, jid)
        if not (contact.subscribed_to or
                contact.pending_out):
            return None
        values = self.get_roster_values(contact)
        contact.subscribed_to = False
        contact.pending_out = None
        contact.stanza_out = ''
        contact.save()
        return values

    @database_sync_to_async
    @atomic_update
    def outbound_unsubscribed(self, user, jid):
        logger.debug('Update: user %s contact %s outbound-unsubscribed',
                     user.user, jid.bare)
        contact = self.retrieve_for_update(user, jid)
        if not contact.in_roster:
            contact.delete()
            return {}
        if not (contact.subscribed_from or
                contact.pending_in or
                contact.preapproved):
            return None
        values = self.get_roster_values(contact)
        contact.subscribed_from = False
        contact.pending_in = None
        contact.stanza_in = ''
        contact.preapproved = False
        contact.save()
        return values
