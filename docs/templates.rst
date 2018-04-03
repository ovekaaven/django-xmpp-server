Templates
=========

You can use the template tags to point your web client at your new XMPP server.

.. _template-tags:

Tags
----
If you load the ``xmpp`` tag set, these tags will be available.

xmpp_bosh_url
    The URL to use for BOSH connections.
    Uses the `XMPP_BOSH_URL` configuration option if set, otherwise deduces
    it from your project's URLconf.

xmpp_websocket_url
    The URL to use for WebSockets connections.
    Uses the `XMPP_WEBSOCKETS_URL` configuration option if set, otherwise
    deduces it from your project's URLconf.

    Note that the URL may be partial, meaning it may not contain a protocol.
    If possible, you should use a different way of telling your web client
    that it should use the WebSockets protocol. Some web clients have
    connection options you can set for this.

    If you really need these URLs to be full (and thus contain the protocol),
    then you can set the `XMPP_SERVER` configuration option, but this is not
    recommended because the browser's same-origin policies may kick in.

xmpp_prebind_url
    The URL to use for BOSH prebinding.
    Uses the `XMPP_BOSH_PREBIND_URL` configuration option if set, otherwise
    deduces it from your project's URLconf.

    An AJAX request to this URL will, if successful, create a new BOSH session
    and return a JSON response with ``jid``, ``sid``, and ``rid`` parameters
    that clients can use to attach to the new BOSH session.

    If the browser is currently logged in to your Django site, then the
    BOSH session will be pre-authenticated with the logged-in Django user.
    If the browser is not logged in, and your configuration allows anonymous
    logins, then the BOSH session will be anonymous.
    Otherwise, the AJAX request will fail with a 403 Forbidden.

xmpp_credentials_url
    The URL to use for generating session tokens.
    Uses the `XMPP_CREDENTIALS_URL` configuration option if set, otherwise
    deduces it from your project's URLconf.

    An AJAX request to this URL will, if successful, return a JSON response
    with ``jid`` and ``password`` parameters that clients can use to
    authenticate to the XMPP server. The password field will contain
    a HMAC-signed session token that's only valid for a limited time,
    and only for the returned JID.
    (The expiration time of session tokens can be set with the
    `XMPP_CREDENTIALS_MAX_AGE` configuration option.)

    If the browser is currently logged in to your Django site, then the
    returned credentials will authenticate the logged-in Django user.
    If the browser is not logged in, the AJAX request will fail with a
    403 Forbidden.

    Clients that use BOSH prebinding do not need session tokens.

xmpp_domain
    The XMPP domain of your server.
    Uses the `XMPP_DOMAIN` configuration option if set, otherwise falls back
    to the Django site domain.

xmpp_jid
    The XMPP JID of the client currently logged in to your Django site.
    If the client is not logged in, a JID without an username is returned.
    (Most web clients will try to log in anonymously if given a JID without
    an username.)


.. _example-converse-js:

Example for Converse.js
-----------------------
`Converse.js`_ is a flexible web client that supports both BOSH and WebSockets.
The following example assumes you want to use Converse.js with automatic login
through session tokens if WebSockets is available, and BOSH prebind otherwise::

    {% load xmpp %}
    <script>
        converse.initialize({
            bosh_service_url: '{% xmpp_bosh_url %}',
            websocket_url: '{% xmpp_websocket_url %}',
            prebind_url: '{% xmpp_prebind_url %}',
            credentials_url: '{% xmpp_credentials_url %}',
            connection_options: { 'protocol': window.WebSocket ? 'wss' : 'https' },
            authentication: window.WebSocket ? 'login' : 'prebind',
            auto_login: true,
            jid: '{% xmpp_jid %}',
            locked_domain: '{% xmpp_domain %}',
            registration_domain: '{% xmpp_domain %}',
        });
    </script>

.. _Converse.js: https://conversejs.org/

.. _example-jsxc:

Example for JSXC
----------------
JSXC_ is an elegant web client that supports BOSH (not WebSockets yet),
but takes a little more work to set up.
The following example shows a possible way of setting up automatic login
through BOSH prebind, assuming you've installed JSXC under ``/static/jsxc/``::

    {% load xmpp %}
    <script>
        $(function() {
          jsxc.init({
            root: '/static/jsxc/',
            xmpp: {
              url: '{% xmpp_bosh_url %}',
              jid: '{% xmpp_jid %}',
              domain: '{% xmpp_domain %}',
            },
          });
        });

        $(document).on('stateChange.jsxc', function(ev, state) {
          if (state === jsxc.CONST.STATE.SUSPEND) {
            $.ajax({
              url: '{% xmpp_prebind_url %}',
              dataType: 'json',
              success: function(data) {
                jsxc.start(data.jid, data.sid, data.rid);
              },
            });
          }
        });
    </script>

.. _JSXC: https://www.jsxc.org/
