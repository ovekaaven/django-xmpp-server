Overview
========

This is an XMPP server that you can integrate with your Django app.

Features
--------
- Supports BOSH, WebSockets, and plain XMPP with TLS

- Customizable integration with Django's user database.

- Scalable, can run on multiple servers.

- Supported authentication methods:

  - Django web session, through any of

    - BOSH prebind
    - session tokens
    - session cookies

  - Plain password
  - Anonymous

- Fully featured example project.

- XMPP extensions supported so far:

  - XEP-0030 Service Discovery
  - XEP-0077 In-Band Registration
  - XEP-0078 Non-SASL Authentication
  - XEP-0124 Bidirectional streams Over Synchronous HTTP (BOSH)
  - XEP-0199 XMPP Ping
  - XEP-0206 XMPP Over BOSH
  - XEP-0280 Message Carbons

(Also, some XMPP extensions are client-to-client and do not necessarily have to
be explicitly supported by the server to work.)

Requirements
------------
- `Python <https://www.python.org/>`_ >= 3.5
- `Django <https://www.djangoproject.com/>`_ >= 1.11
  (but other frameworks might be supported in the future)
- `channels <https://channels.readthedocs.io/en/latest/>`_ >= 2.0.2
- `slixmpp <https://slixmpp.readthedocs.io/>`_
- `defusedxml <https://github.com/tiran/defusedxml>`_ (if you want protection against XML bombs)
- some ASGI host, e.g. `daphne <https://github.com/django/daphne>`_
- some channel layer, e.g. `channels_redis <https://github.com/django/channels_redis>`_
  (you *can* use the in-memory channel layer that comes with ``channels``,
  but only if you don't plan to run more than one Django server instance)

Optional:

- Twisted (if you plan to support plain XMPP,
  which may include connecting external server components)
- pyOpenSSL (if you plan to support plain XMPP with TLS)
