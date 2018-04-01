from asgiref.sync import async_to_sync
from django.core.signing import TimestampSigner
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render
from .templatetags.xmpp import get_chat_domain
from .xmpp.bosh import prebind_bosh_stream
from .conf import settings
from .hooks import get_hook

def prebind_view(request):
    if request.user.is_authenticated:
        username = get_hook('auth').get_webuser_username(request.user)
    elif settings.ALLOW_ANONYMOUS_LOGIN:
        username = None
    else:
        return HttpResponseForbidden()
    domain = get_chat_domain(request)
    host = request.get_host()
    origin = request.META.get('HTTP_ORIGIN')
    if origin is None:
        scheme = 'https://' if request.is_secure() else 'http://'
        origin = scheme + host
    if settings.CHAT_SERVER:
        host = settings.CHAT_SERVER
    prebind_func = async_to_sync(prebind_bosh_stream)
    data = prebind_func(request.user,
                        username=username,
                        domain=domain,
                        host=host,
                        origin=origin)
    return JsonResponse(data)

def credentials_view(request):
    if not request.user.is_authenticated:
        return HttpResponseForbidden()
    username = get_hook('auth').get_webuser_username(request.user)
    if not username:
        return HttpResponseForbidden()
    domain = get_chat_domain(request)
    jid = '%s@%s' % (username, domain)
    token = TimestampSigner(salt='xmppserver.credentials').sign(jid)
    return JsonResponse({'jid': jid, 'password': '//jid/' + token})

def chat_view(request):
    return render(request, 'xmppserver/chat.html')
