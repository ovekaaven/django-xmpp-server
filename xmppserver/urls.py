from django.conf.urls import url
from .consumers import BOSHConsumer, WSConsumer
from .views import prebind_view, credentials_view, chat_view

app_name = 'xmppserver'

# BOSH and WS should have the same URL, so that clients
# can choose whichever method works for them
http_urls = [
    url(r'^bind/$', BOSHConsumer, name='bosh'),
]

ws_urls = [
    url(r'^bind/$', WSConsumer, name='ws'),
]

urlpatterns = [
    url(r'^prebind/$', prebind_view, name='prebind'),
    url(r'^credentials/$', credentials_view, name='credentials'),
    url(r'^$', chat_view, name='chat'),
]
