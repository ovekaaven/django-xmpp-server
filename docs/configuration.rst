.. _configuration:

Configuration
=============

All configuration options have usable (but not necessarily useful) defaults.

Basic options
-------------
.. autoflatclass:: xmppserver.conf.Settings
    :add-prefix: XMPP_
    :members: DOMAIN, ALLOW_REGISTRATION, REGISTRATION_URL

Authentication
--------------
.. autoflatclass:: xmppserver.conf.Settings
    :add-prefix: XMPP_
    :exclude-members: ALLOW_REGISTRATION
    :filter-prefix: ALLOW, CREDENTIALS
    :members:

BOSH
----
.. autoflatclass:: xmppserver.conf.Settings
    :add-prefix: XMPP_
    :filter-prefix: BOSH
    :members:

WebSockets
----------
.. autoflatclass:: xmppserver.conf.Settings
    :add-prefix: XMPP_
    :filter-prefix: WEBSOCKETS
    :members:

Plain XMPP
----------
.. autoflatclass:: xmppserver.conf.Settings
    :add-prefix: XMPP_
    :filter-prefix: TCP, TLS
    :members:

Other
-----
.. autoflatclass:: xmppserver.conf.Settings
    :add-prefix: XMPP_
    :filter-prefix: SERVER
    :members:
