from django.db import models
from django.utils.translation import pgettext_lazy

class XMPPContact(models.Model):
    username = models.CharField(max_length=1023,
        verbose_name=pgettext_lazy('xmpp', 'username'))
    contact = models.CharField(max_length=2047,
        verbose_name=pgettext_lazy('xmpp', 'contact'))
    in_roster = models.BooleanField(
        verbose_name=pgettext_lazy('xmpp', 'in roster'),
        default=False)
    name = models.CharField(max_length=1023,
        verbose_name=pgettext_lazy('xmpp', 'name'),
        blank=True)
    subscribed_from = models.BooleanField(
        verbose_name=pgettext_lazy('xmpp', 'subscribed from'),
        default=False)
    subscribed_to = models.BooleanField(
        verbose_name=pgettext_lazy('xmpp', 'subscribed to'),
        default=False)
    preapproved = models.BooleanField(
        verbose_name=pgettext_lazy('xmpp', 'pre-approved'),
        default=False)
    pending_in = models.DateTimeField(
        verbose_name=pgettext_lazy('xmpp', 'pending-in'),
        null=True, blank=True)
    pending_out = models.DateTimeField(
        verbose_name=pgettext_lazy('xmpp', 'pending-out'),
        null=True, blank=True)
    groups = models.TextField(
        verbose_name=pgettext_lazy('xmpp', 'groups'),
        blank=True)
    stanza_in = models.TextField(
        verbose_name=pgettext_lazy('xmpp', 'pending-in stanza'),
        blank=True)
    stanza_out = models.TextField(
        verbose_name=pgettext_lazy('xmpp', 'pending-out stanza'),
        blank=True)

    class Meta:
        verbose_name = pgettext_lazy('xmpp', 'contact')
        verbose_name_plural = pgettext_lazy('xmpp', 'contacts')
        unique_together = ('username', 'contact')

    def __str__(self):
        return "%s/%s" % (self.username, self.contact)
