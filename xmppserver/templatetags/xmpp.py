from django import template
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from ..conf import settings
from ..hooks import get_hook

register = template.Library()

def get_chat_domain(request):
    domain = settings.DOMAIN
    if domain:
        return domain
    return get_current_site(request).domain

@register.simple_tag
def xmpp_bosh_url():
    url = settings.BOSH_URL
    if url:
        return url
    server = settings.SERVER
    path = reverse('xmppserver:chat') + 'bind/'
    if server:
        scheme = 'https' if settings.SERVER_SECURE else 'http'
        return '%s://%s%s' % (scheme, server, path)
    else:
        return path

@register.simple_tag
def xmpp_websocket_url():
    url = settings.WEBSOCKETS_URL
    if url:
        return url
    server = settings.SERVER
    path = reverse('xmppserver:chat') + 'bind/'
    if server:
        scheme = 'wss' if settings.SERVER_SECURE else 'ws'
        return '%s://%s%s' % (scheme, server, path)
    else:
        return path

@register.simple_tag
def xmpp_prebind_url():
    url = settings.BOSH_PREBIND_URL
    if url:
        return url
    return reverse('xmppserver:prebind')

@register.simple_tag
def xmpp_credentials_url():
    url = settings.CREDENTIALS_URL
    if url:
        return url
    return reverse('xmppserver:credentials')

@register.simple_tag(takes_context=True)
def xmpp_domain(context):
    request = context.get('request', None)
    if not request:
        return ''
    return get_chat_domain(request)

@register.simple_tag(takes_context=True)
def xmpp_jid(context):
    request = context.get('request', None)
    if not request:
        return ''
    user = request.user
    domain = get_chat_domain(request)
    if user.is_authenticated:
        username = get_hook('auth').get_webuser_username(user)
        return '%s@%s' % (username, domain)
    else:
        return domain
