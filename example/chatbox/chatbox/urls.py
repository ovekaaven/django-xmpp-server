from django.contrib import admin
from django.urls import include, path
from .views import ChatView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('chat/', include('xmppserver.urls')),
    path('', ChatView.as_view())
]
