from django.conf import settings as django_settings
from django.dispatch import receiver
from django.db.models.signals import post_delete

# In order to be flexible, the main module should not define
# any models, that should only be done by optional submodules.

# However, this is a good place to register signal receivers
# for Django's user model, so that we can clean up stuff.

class FakeRequest:
    @staticmethod
    def get_host():
        # if the user hasn't configured anything else...
        return 'localhost'

def get_chat_domain():
    from .conf import settings
    domain = settings.DOMAIN
    if domain:
        return domain
    from django.contrib.sites.shortcuts import get_current_site
    return get_current_site(FakeRequest).domain

@receiver(post_delete, sender=django_settings.AUTH_USER_MODEL)
def user_deleted(sender, instance, **kwargs):
    from .hooks import get_hook
    auth_hook = get_hook('auth')
    username = auth_hook.get_webuser_username(instance)
    if username is not None:
        from .xmpp.dummy import DummyStream
        # The DummyStream is able to access the database
        # and communicate with other XMPP streams.
        # Just tell it that the user is gone.
        stream = DummyStream()
        stream.boundjid.username = username
        stream.boundjid.domain = get_chat_domain()
        stream.user_deleted()
        stream.dispose()
