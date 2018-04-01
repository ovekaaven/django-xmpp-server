from django.conf import settings as django_settings

class Settings(object):
    def __getattribute__(self, attr):
        if attr == attr.upper():
            try:
                # try django settings first
                return getattr(django_settings, 'XMPP_' + attr)
            except AttributeError:
                # fallback to our defaults
                pass
        return super(Settings, self).__getattribute__(attr)

    DOMAIN = None
    """
    XMPP domain name of your server. Should normally be set to your primary
    domain name. If you do not set this, the server will resort to using
    the domain name provided by the client.
    """

    ALLOW_REGISTRATION = False
    """
    Whether to allow in-band registration (XEP-0077). Enabling this will allow
    anyone to create users on your Django site through XMPP, unless you restrict
    it with a custom :ref:`authentication hook <hooks>`.
    """

    REGISTRATION_URL = None
    """
    URL to your user registration page. If you do not allow in-band registration,
    users who want to register will be told to visit this URL instead.
    If unset, an URL will be constructed from the XMPP domain.
    """

    ALLOW_ANONYMOUS_LOGIN = False
    """
    Whether to allow anonymous logins.
    """

    ALLOW_PLAIN_PASSWORD = True
    """
    Whether to allow XMPP authentication with plaintext passwords.
    If you use HTTPS, then this is typically OK.
    """

    ALLOW_WEBUSER_LOGIN = True
    """
    Whether to allow XMPP authentication through session cookies.
    The XMPP client must supply an empty password, otherwise regular
    password checking is done.
    This option does not apply if you're relying on BOSH prebinding
    or session tokens. If so, you may want to set it to False,
    to avoid redundant Django session database lookups.
    """

    ALLOW_LEGACY_AUTH = False
    """
    Whether to allow non-SASL authentication (XEP-0078). This is a compatibility
    option and should normally not be needed.
    """

    CREDENTIALS_URL = None
    """
    The URL to the session token generation view. Used by the template tags.
    To avoid issues with browser same-origin policies, this URL should not
    have a hostname.
    If unset, the URL will be deduced from your project's URLconf.
    """

    CREDENTIALS_MAX_AGE = 30
    """
    Expiration time, in seconds, of session tokens. Should only be long enough
    for the XMPP client to retrieve a token and use it to log in. Currently,
    these are stateless HMAC tokens, meaning they could be used more than once.
    To reduce the chances of this, the expiration time should be short.
    (Unless you use an :ref:`authentication hook <hooks>` that makes sure tokens
    can only be used once, but xmppserver does not currently provide such a hook.)
    """

    BOSH_URL = None
    """
    The URL to the BOSH consumer. Used by the template tags.
    If unset, the URL will be deduced from your project's URLconf.
    """

    BOSH_PREBIND_URL = None
    """
    The URL to the BOSH prebind view. Used by the template tags.
    To avoid issues with browser same-origin policies, this URL should not
    have a hostname.
    If unset, the URL will be deduced from your project's URLconf.
    """

    BOSH_MIN_WAIT = 10
    """
    Minimum allowed wait time for BOSH requests, in seconds.
    Lower values may improve reliability slightly, but
    also increase bandwidth usage and server load.
    """

    BOSH_MAX_WAIT = 60
    """
    Maximum allowed wait time for BOSH requests, in seconds.
    Lower values may improve reliability slightly, but
    also increase bandwidth usage and server load.
    """

    BOSH_MAX_HOLD = 2
    """
    Maximum number of waiting BOSH requests.
    Higher values may improve throughput slightly,
    but also increase server load.
    """

    BOSH_MAX_INACTIVITY = 120
    """
    Time before an inactive BOSH client is presumed dead, in seconds.
    """

    WEBSOCKETS_URL = None
    """
    The URL to the WebSockets consumer. Used by the template tags.
    If unset, the URL will be deduced from your project's URLconf.
    """

    TCP_SERVER = True
    """
    Whether to allow starting the plain XMPP server. To actually start it,
    you must also add the following to your ``routing.py``::

        from xmppserver import xmpp_server
        xmpp_server.start_xmpp_server()
    """

    TCP_CLIENT_PORT = 5222
    """
    The XMPP client-to-server port to listen on.
    """

    TCP_SERVER_PORT = 5269
    """
    The XMPP server-to-server port to listen on.
    This feature is not yet implemented.
    """

    TCP_REQUIRE_TLS = True
    """
    Whether to require TLS-secured connections.
    """

    TLS_CERT_PATH = None
    """
    Path to the X.509 certificate, in PEM format. Required for TLS.
    """

    TLS_PRIV_KEY_PATH = None
    """
    Path to the X.509 private key, in PEM format. Required for TLS.
    """

    TLS_CACERT_PATHS = []
    """
    Paths to CA certificates to be used for validating client certificates,
    in PEM format.
    This feature is not yet implemented.
    """

    SERVER = None
    """
    If you need the template tags to return a full URL, you can set this to
    the hostname of your XMPP server. You shouldn't do this unless you have to,
    since the browser's same-origin policies may kick in. The XMPP Server
    does alleviate this by supporting CORS, but not all browsers support it.
    And even if they do, BOSH connections will take longer to establish.
    (WebSockets are not affected, though.)
    """

    SERVER_SECURE = True
    """
    Whether your XMPP server uses HTTPS. Used by the template tags
    if XMPP_SERVER is set.
    """


settings = Settings()
