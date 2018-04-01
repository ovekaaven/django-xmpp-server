from django.conf.urls import include, url
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.http import AsgiHandler
from xmppserver import urls as xmpp_urls, xmpp_server

application = ProtocolTypeRouter({
    'http': URLRouter([
        url(r'^chat/', include(xmpp_urls.http_urls)),
        url(r'', AsgiHandler)
    ]),
    'websocket': URLRouter([
        url(r'^chat/', include(xmpp_urls.ws_urls))
    ])
})

xmpp_server.start_xmpp_server()
