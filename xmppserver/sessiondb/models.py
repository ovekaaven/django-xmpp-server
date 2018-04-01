from django.db import models
from django.utils.translation import pgettext_lazy

class XMPPSession(models.Model):
    username = models.CharField(max_length=1023,
        verbose_name=pgettext_lazy('xmpp', 'username'))
    resource = models.CharField(max_length=1023,
        verbose_name=pgettext_lazy('xmpp', 'resource'))
    priority = models.SmallIntegerField(
        verbose_name=pgettext_lazy('xmpp', 'priority'),
        null=True, blank=True)
    stanza = models.TextField(
        verbose_name=pgettext_lazy('xmpp', 'last presence stanza'),
        blank=True)
    login_time = models.DateTimeField(
        verbose_name=pgettext_lazy('xmpp', 'time of login'),
        auto_now_add=True)
    update_time = models.DateTimeField(
        verbose_name=pgettext_lazy('xmpp', 'time of last update'),
        auto_now=True)
    server_id = models.CharField(max_length=64,
        verbose_name=pgettext_lazy('xmpp', 'server ID'),
        blank=True, db_index=True)

    class Meta:
        verbose_name = pgettext_lazy('xmpp', 'session')
        verbose_name_plural = pgettext_lazy('xmpp', 'sessions')
        unique_together = ('username', 'resource')
        db_tablespace = 'xmppsession'

    def __str__(self):
        return "%s/%s" % (self.username, self.resource)
