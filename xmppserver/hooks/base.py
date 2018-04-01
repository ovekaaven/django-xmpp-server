class BaseAuthHook(object):
    """
    These hooks have type 'auth', and hook instances are available as
    ``stream.auth_hook``. The default hook (DefaultAuthHook) implements
    authentication for user models supported by ``django.contrib.auth``.
    This should cover the need of many projects, but if it doesn't cover
    yours, you can write your own hook.

    The default hook keeps track of the currently authenticated Django user
    in ``self.user``, and for the convenience of other hooks and plugins,
    also stores it in ``stream.bound_user`` once the stream is bound.
    """

    async def bind(self, stream):
        """
        Prepare to bind the stream. The client has authenticated,
        but has not yet requested a resource identifier for the stream.
        The bare JID is available in ``stream.boundjid``.

        :param stream: XMPP stream object
        """
        pass

    async def unbind(self, stream):
        """
        Unbind the stream.
        The connection to the client has been closed or lost.

        :param stream: XMPP stream object
        """
        pass

    @staticmethod
    def get_webuser_username(user):
        """
        Get the XMPP username of a Django user.
        The default hook calls ``user.get_username()``.

        This method must be synchronous and static. It may be called from a Django
        view in order to generate credentials before an XMPP stream is opened,
        or from a Django signal receiver when the user is being deleted.

        :param user: Django user object
        :return: XMPP username
        """
        return None

    @staticmethod
    def get_webuser_by_username(username):
        """
        Get the Django user of an XMPP username.
        The default hook calls ``get_user_model().objects.get_by_natural_key(username)``.

        This method must be synchronous.

        :param str username: XMPP username
        :return: Django user object
        :raise ObjectDoesNotExist: If user does not exist
        """
        return None

    async def check_webuser(self, stream, user, username):
        """
        Authenticate using Django session cookies.
        The Django user identified by the session cookies is provided, but the
        object may be lazy, so checking it may result in a database access.
        The default hook checks whether the Django user is authenticated, and that
        the Django user's XMPP username matches the XMPP client's username.

        :param user: Django user object
        :param str username: Username requested by XMPP client
        :return: True if authentication is successful
        """
        return False

    async def check_token(self, stream, username, token):
        """
        Authenticate using a session token.
        The default hook validates the token's HMAC signature and timestamp,
        and checks whether the Django user is active.

        :param str username: Username requested by XMPP client
        :param str token: Token provided by XMPP client
        :return: True if authentication is successful
        """
        return True

    async def check_password(self, stream, username, password):
        """
        Authenticate using a plaintext password.
        Should return True if authentication was successful.
        The default hook checks the password, and whether the Django user
        is active.

        :param str username: Username requested by XMPP client
        :param str password: Password provided by XMPP client
        :return: True if authentication is successful
        """
        return False

    async def valid_contact(self, username):
        """
        Check whether the given XMPP username exists and could be
        contacted by the bound user.
        The default hook checks whether the Django user is active.

        :param str username: XMPP username
        :return: True if the contact exists
        """
        return False

    async def create_user(self, username, password):
        """
        Register a new user.
        Only used if the `XMPP_ALLOW_REGISTRATION` configuration option is enabled.

        :param str username: Username requested by XMPP client
        :param str password: Password requested by XMPP client
        :return: True if successful, False if username already exists
        :raise XMPPError: If unsuccessful for any other reason
        """
        raise NotImplementedError()

    async def change_password(self, password):
        """
        Change the bound user's password.
        Only used if the `XMPP_ALLOW_REGISTRATION` configuration option is enabled.

        :param str password: Password requested by XMPP client
        :raise XMPPError: If unsuccessful
        """
        raise NotImplementedError()

    async def delete_user(self):
        """
        Delete the bound user.
        Only used if the `XMPP_ALLOW_REGISTRATION` configuration option is enabled.

        :raise XMPPError: If unsuccessful
        """
        raise NotImplementedError()

class BaseRosterHook(object):
    """
    These hooks have type 'roster', and hook instances are available as
    ``stream.roster_hook``. The default hook (DefaultRosterHook) doesn't
    do anything, but xmppserver comes with two alternatives:

    1.  If you're just making a simple helpdesk or community app, one of
        the `alternative hooks <alternative-hooks>` might work for you.

    2.  If you wish to have a full-featured XMPP server, then you can
        add ``'xmppserver.rosterdb'`` to your ``INSTALLED_APPS``.
        It installs a full-featured roster hook, backed by your database.

    Or if you want, you can write your own hook.
    """

    async def bind(self, stream):
        """
        The stream has been bound. The client has authenticated and assigned
        a resource identifier to the stream, and now needs its roster.
        The client's full JID is available as ``stream.boundjid``.

        :param stream: XMPP stream object
        """
        pass

    async def unbind(self, stream):
        """
        Unbind the stream.
        The connection to the client has been closed or lost.

        :param stream: XMPP stream object
        """
        pass

    async def get_contacts(self, user):
        """
        Get the roster fields of all the contacts of the given user.

        The roster is represented as a sequence of (jid, values) tuples,
        where the values are dictionaries with XMPP roster fields,
        such as 'name', 'groups', and 'subscription'.

        If subscription would be 'none', then this method can omit
        the field for brevity, but the other hook methods should not
        do so.

        :param JID user: User JID
        :return: Roster sequence, or None if roster doesn't exist
        """
        return None

    async def get_contact(self, user, jid):
        """
        Get the roster fields of a specific contact of the given user.

        Since this method may be involved in roster pushes, the
        'subscription' field must be included, even when it is 'none'.

        :param JID user: User JID
        :param JID jid: Contact JID
        :return: Roster fields, or None if contact doesn't exist
        :raise XMPPError: If unsuccessful
        """
        return None

    async def update_contact(self, user, jid, values):
        """
        Create or update a contact on behalf of the given user.
        The method should only change names and groups, not subscriptions.

        :param JID user: User JID
        :param JID jid: Contact JID
        :param values: Roster fields requested by XMPP client
        :return: Updated roster fields
        :raise XMPPError: If unsuccessful
        """
        return None

    async def remove_contact(self, user, jid):
        """
        Delete a contact on behalf of the given user.
        The method should verify that there are no active subscriptions
        from or to the contact (and that it's not in the Pending-Out state
        either), before deleting it from the roster.

        :param JID user: User JID
        :param JID jid: Contact JID
        :return: True if successful, False if subscriptions exist, or None if contact doesn't exist
        :raise XMPPError: If unsuccessful
        """
        return None

    async def get_pending(self, user):
        """
        Get all (potential) contacts of the given user that are
        currently in the Pending-In state.

        :param JID user: User JID
        :return: Sequence of (JID, stanza) tuples, or None
        """
        return None

    async def is_pending(self, user, jid):
        """
        Returns whether a specific (potential) contact is currently
        in the Pending-In state.

        :param JID user: User JID
        :return: True if pending, False if not pending, or None if contact doesn't exist
        """
        return None

    async def inbound_subscribe(self, user, jid, stanza=''):
        """
        Transition a (potential) contact into the Pending-In state,
        unless a subscription from the contact already exists.
        If the contact is pre-approved, then instead accept the
        'from' subscription.

        If the contact isn't in the roster yet, it should not be
        added to it, but tracked outside of the roster until the
        user either adds the contact or denies the request.

        :param JID user: User JID
        :param JID jid: Contact JID
        :param stanza: Presence stanza as an XML string
        :return: New roster fields if pre-approved, True if now pending,
                 False if already pending, or None if already subscribed
        :raise XMPPError: If unsuccessful
        """
        return None

    async def inbound_subscribed(self, user, jid):
        """
        Transition a contact out of the Pending-Out state,
        and add the 'to' subscription.

        :param JID user: User JID
        :param JID jid: Contact JID
        :return: New roster fields, or None if subscription was not pending
        :raise XMPPError: If unsuccessful
        """
        return None

    async def inbound_unsubscribe(self, user, jid):
        """
        Cancel a Pending-In state or an active 'from' subscription.

        :param JID user: User JID
        :param JID jid: Contact JID
        :return: Old roster fields, or None if already unsubscribed
        :raise XMPPError: If unsuccessful
        """
        return None

    async def inbound_unsubscribed(self, user, jid):
        """
        Cancel a Pending-Out state or an active 'to' subscription.

        :param JID user: User JID
        :param JID jid: Contact JID
        :return: Old roster fields, or None if already unsubscribed
        :raise XMPPError: If unsuccessful
        """
        return None

    async def outbound_subscribe(self, user, jid, stanza=''):
        """
        Transition a contact into the Pending-Out state
        (creating it if necessary), unless a subscription to
        the contact already exists.

        :param JID user: User JID
        :param JID jid: Contact JID
        :param stanza: Presence stanza as an XML string
        :return: New roster fields, or None if already subscribed
        :raise XMPPError: If unsuccessful
        """
        return None

    async def outbound_subscribed(self, user, jid):
        """
        Transition a contact out of the Pending-In state,
        and add the 'from' subscription (creating it if necessary).
        If no subscription is pending or active yet,
        then pre-approve the contact (creating it if necessary).

        :param JID user: User JID
        :param JID jid: Contact JID
        :return: New roster fields, or None if already subscribed
        :raise XMPPError: If unsuccessful
        """
        return None

    async def outbound_unsubscribe(self, user, jid):
        """
        Cancel a Pending-Out state or an active 'to' subscription.

        :param JID user: User JID
        :param JID jid: Contact JID
        :return: Old roster fields, or None if already unsubscribed
        :raise XMPPError: If unsuccessful
        """
        return None

    async def outbound_unsubscribed(self, user, jid):
        """
        Cancel a Pending-In state, an active 'from' subscription,
        or a pre-approval.

        :param JID user: User JID
        :param JID jid: Contact JID
        :return: Old roster fields, or None if already unsubscribed
        :raise XMPPError: If unsuccessful
        """
        return None

class BaseSessionHook(object):
    """
    These hooks have type 'session', and hook instances are available as
    ``stream.session_hook``. The default hook (DefaultSessionHook) doesn't
    do much other than creating session IDs. If you use it, the server does
    work, but with a somewhat reduced feature set.
    Presence should mostly work (because the server will fall back to XMPP
    presence probes if the session database isn't available), but things like
    resource discovery and session management might not. Currently, sending
    messages to users that are offline would also not result in error messages.

    If you wish to have a full-featured XMPP server, then you can add
    ``'xmppserver.sessiondb'`` to your ``INSTALLED_APPS``.
    It installs a full-featured session hook, backed by your database.
    **HOWEVER**, using your database for session data could be slow.
    It may be better to use a session hook that uses something like
    Redis instead, but xmppserver does not currently provide such a hook.
    """

    async def bind(self, stream):
        """
        Bind the stream. The client has authenticated and requested a
        resource identifier for the stream.
        The requested full JID is available as ``stream.boundjid``.
        The method should verify that the requested resource is not
        already bound by a different stream.

        :param stream: XMPP stream object
        :return: True if successful, False if the resource is in use
        :raise XMPPError: If unsuccessful
        """
        return None

    async def unbind(self, stream):
        """
        Unbind the stream.
        The connection to the client has been closed or lost.

        :param stream: XMPP stream object
        """
        pass

    async def set_presence(self, priority, stanza=None):
        """
        Set priority and availability of the bound stream.

        :param priority: Presence priority if available, or None if unavailable
        :param stanza: Presence stanza as an XML string, or None
        """
        pass

    async def get_presence(self, jid):
        """
        Retrieve priority and availability of a specific resource.

        :param JID jid: Full JID
        :return: (priority, stanza) tuple, or None if unavailable
        """
        return None

    async def get_all_presences(self, username):
        """
        Retrieve priorities and availabilities of all resources
        belonging to a given user.

        :param username: XMPP username
        :return: Sequence of (resource, priority, stanza) tuples
        """
        return None

    async def get_all_roster_presences(self, usernames):
        """
        Retrieve priorities and availabilities of all resources
        belonging to any of the given users. Implementing this
        method is optional, but may speed up roster queries.

        :param usernames: List of usernames
        :return: Sequence of (username, resource, priority, stanza) tuples
        """
        return None

    async def get_resource(self, jid):
        """
        Retrieve priority of a specific resource.

        :param JID jid: Full JID
        :return: Presence priority if available, or None if unavailable
        """
        return None

    async def get_all_resources(self, username):
        """
        Retrieve priorities of all resources belonging to a given user.

        :param username: XMPP username
        :return: Sequence of (resource, priority) tuples
        """
        return None

    async def get_preferred_resource(self, username):
        """
        Retrieve the resource with the highest priority among all
        available resources with non-negative priorities that
        belongs to a given user.

        It's also possible to return an empty string in order to
        broadcast to all available resources.

        :param username: XMPP username
        :return: Resource, or None if no such resource exists
        """
        return None

    async def kill_resource(self, jid):
        """
        Remove binding records of a specific resource.
        Used if the server hosting the corresponding stream
        seems to have crashed.

        :param JID jid: Full JID
        """
        pass
