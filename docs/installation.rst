Installation
============

First, make sure you've `configured Django Channels`_.

.. _configured Django Channels: https://channels.readthedocs.io/en/latest/installation.html

.. _channel layer: https://channels.readthedocs.io/en/latest/topics/channel_layers.html

You must also configure a `channel layer`_ that the XMPP server can use. If you only
need to run a single server process, you can start with the basic in-memory channel layer
(you can change it later)::

    CHANNEL_LAYERS = {
        'xmppserver': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
            'CONFIG': {},
        }
    }

Install the Python package::

    pip install django-xmpp-server

If you plan to support the plain XMPP protocol, use::

    pip install django-xmpp-server[tcp]

Add ``xmppserver``, and any subcomponents you need, to your INSTALLED_APPS setting::

    INSTALLED_APPS = [
        ...
        'channels',
        ...
        'xmppserver',
        'xmppserver.sessiondb', # optional
        'xmppserver.rosterdb',  # optional
    ]

For something like a simple helpdesk or community server, you might not need
the optional components, and installing them would just slow the server down.
Instead, you can just configure an `alternative roster hook <alternative-hooks>`.

However, if you plan to run a fully-fledged XMPP server, then you should
consider installing them, or third-party equivalents. (For example, while
``xmppserver.sessiondb`` uses your database for convenience, a session component
that used Redis would probably be faster and scale better.)

Add the appropriate entries to your project's ``routing.py``, for example::

    from django.conf.urls import include, url
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.http import AsgiHandler
    from xmppserver import urls as xmpp_urls

    application = ProtocolTypeRouter({
        'http': URLRouter([
            url(r'^chat/', include(xmpp_urls.http_urls)),
            url(r'', AsgiHandler)
        ]),
        'websocket': URLRouter([
            url(r'^chat/', include(xmpp_urls.ws_urls))
        ])
    })

    # if you want to run the plain XMPP server
    from xmppserver import xmpp_server
    xmpp_server.start_xmpp_server()

Depending on your use case, you may also need to add the xmppserver
URLconf to your project's ``urls.py``::

    url(r'^chat/', include('xmppserver.urls')),

Post-installation
-----------------
If you've installed the optional components, then you will need to run
a migration::

    ./manage.py migrate

Example project
---------------
If you want an example project to get you started, or just for testing,
you can find the 'chatbox' example in the source code on GitHub:

https://github.com/ovekaaven/django-xmpp-server
