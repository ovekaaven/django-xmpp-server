from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _

class ChatserverConfig(AppConfig):
    name = 'xmppserver'
    verbose_name = _('XMPP Server')
