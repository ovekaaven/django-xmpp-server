from django.contrib import admin
from django.utils.translation import pgettext_lazy
from .models import XMPPSession

class SessionAdmin(admin.ModelAdmin):
    list_display = ('username', 'resource', 'priority',
                    'login_time', 'update_time', 'server_id')
    list_display_links = ('username', 'resource')
    list_filter = ('server_id',)
    ordering = ('username',)
    readonly_fields = ('login_time', 'update_time')

class Session(XMPPSession):
    # proxy to set app_label in admin
    class Meta:
        proxy = True
        app_label = 'xmppserver'
        verbose_name = pgettext_lazy('xmpp', 'session')
        verbose_name_plural = pgettext_lazy('xmpp', 'sessions')

admin.site.register(Session, SessionAdmin)
