from django.apps import AppConfig
from django.utils.translation import pgettext_lazy

class RosterDBConfig(AppConfig):
    name = 'xmppserver.rosterdb'
    verbose_name = pgettext_lazy('xmpp', 'XMPP Rosters')

    def ready(self):
        from .hook import RosterHook
        from ..hooks import set_hook
        set_hook('roster', RosterHook, priority=1)
