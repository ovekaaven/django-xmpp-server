from channels.db import database_sync_to_async
from django.db import IntegrityError
from .models import XMPPSession
from ..hooks import DefaultSessionHook
from ..utils import get_server_addr
import logging

logger = logging.getLogger('xmppserver.rosterdb')
server_addr = get_server_addr()

def clear_old_sessions():
    # this function is used to clear orphaned sessions if the
    # server seems to have restarted (very common when using
    # the auto-reloading "runserver" command)
    logger.info('Clearing old sessions belonging to %s', server_addr)
    try:
        (XMPPSession.objects.
         filter(server_id=server_addr).
         delete())
    except:
        # database might not exist yet
        pass

class SessionHook(DefaultSessionHook):

    def __init__(self):
        self.obj = None

    def destroy_session(self):
        if self.obj is not None:
            logger.debug('Unbind: resource %s', self.jid.full)
            self.obj.delete()
            self.obj = None
        self.jid = None

    @database_sync_to_async
    def bind(self, stream):
        self.destroy_session() # just in case
        jid = stream.boundjid
        logger.debug('Bind: resource %s', jid.full)
        try:
            self.obj = (XMPPSession.objects.
                        create(username=jid.user,
                               resource=jid.resource,
                               server_id=server_addr))
        except IntegrityError:
            logger.debug('Database integrity error when binding resource %s', jid.full)
            return False
        self.jid = jid
        return True

    @database_sync_to_async
    def unbind(self, stream):
        self.destroy_session()

    @database_sync_to_async
    def set_presence(self, priority, stanza=None):
        logger.debug('Update: resource %s presence', self.jid.full)
        self.obj.priority = priority
        self.obj.stanza = stanza or ''
        self.obj.save()

    @database_sync_to_async
    def get_presence(self, jid):
        logger.debug('Retrieve: resource %s presence', jid.full)
        return (XMPPSession.objects.
                filter(username=jid.user,
                       resource=jid.resource).
                values_list('priority',
                            'stanza').
                first())

    @database_sync_to_async
    def get_all_presences(self, username):
        logger.debug('Retrieve: user %s presences', username)
        return list(XMPPSession.objects.
                    filter(username=username,
                           priority__isnull=False).
                    values_list('resource',
                                'priority',
                                'stanza'))

    @database_sync_to_async
    def get_all_roster_presences(self, usernames):
        logger.debug('Retrieve: user %s roster presences', self.jid.user)
        return list(XMPPSession.objects.
                    filter(username__in=usernames,
                           priority__isnull=False).
                    values_list('username',
                                'resource',
                                'priority',
                                'stanza'))

    @database_sync_to_async
    def get_resource(self, jid):
        logger.debug('Retrieve: resource %s availability', jid.full)
        return (XMPPSession.objects.
                filter(username=jid.user,
                       resource=jid.resource).
                values_list('priority', flat=True).
                first())

    @database_sync_to_async
    def get_all_resources(self, username):
        logger.debug('Retrieve: user %s availabilities', username)
        return list(XMPPSession.objects.
                    filter(username=username,
                           priority__isnull=False).
                    values_list('resource',
                                'priority'))

    @database_sync_to_async
    def get_preferred_resource(self, username):
        logger.debug('Retrieve: user %s preferred resource', username)
        return (XMPPSession.objects.
                filter(username=username,
                       priority__gte=0).
                order_by('-priority').
                values_list('resource', flat=True).
                first())

    @database_sync_to_async
    def kill_resource(self, jid):
        logger.debug('Kill: resource %s', jid.full)
        (XMPPSession.objects.
         filter(username=jid.user,
                resource=jid.resource).
         delete())
