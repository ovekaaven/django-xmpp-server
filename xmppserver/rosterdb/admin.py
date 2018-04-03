from django.contrib import admin
from django.utils.translation import pgettext_lazy
from .models import XMPPContact

class ContactAdmin(admin.ModelAdmin):
    list_display = ('username', 'contact', 'in_roster',
                    'subscribed_from', 'subscribed_to',
                    'pending_in', 'pending_out',
                    'name')
    list_display_links = ('username', 'contact')
    ordering = ('username',)

class Contact(XMPPContact):
    # proxy to set app_label in admin
    class Meta:
        proxy = True
        app_label = 'xmppserver'
        verbose_name = pgettext_lazy('xmpp', 'contact')
        verbose_name_plural = pgettext_lazy('xmpp', 'contacts')

admin.site.register(Contact, ContactAdmin)
