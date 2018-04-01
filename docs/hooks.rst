.. _hooks:

Hooks
=====

You can customize certain XMPP Server behaviour by installing hooks,
in the form of classes that implement the behaviour you want.

For example, say you wanted the XMPP username to be independent of the
Django username, and made a custom user model with an ``xmpp_username``
field. Then you could install an 'auth' hook as follows::

    from xmppserver import hooks

    class MyAuthHook(hooks.DefaultAuthHook):
        @staticmethod
        def get_webuser_username(user):
            return user.xmpp_username

        @staticmethod
        def get_webuser_by_username(username):
            return MyUserModel.objects.get(xmpp_username=username)

    hooks.set_hook('auth', MyAuthHook)

If you're writing a reusable app, a good place to install hooks from may be your app's
``AppConfig.ready`` method (see the `Django documentation`_). Otherwise, you can do
it from more or less any module that's loaded on startup, such as your ``routing.py``.

.. _Django documentation: https://docs.djangoproject.com/en/2.0/ref/applications/

Only one hook can be installed for each hook type. If more than one app might
want to install a hook of the same type, they can specify a priority.
`set_hook` will then install the hook that has the highest priority.

.. _alternative-hooks:

Alternative hooks
-----------------
xmppserver comes with two non-default roster hooks that may be useful
if you're just making a simple helpdesk or community app.
The :py:class:`xmppserver.hooks.roster.EveryoneRosterHook` returns all
Django users, and :py:class:`xmppserver.hooks.roster.StaffRosterHook`
returns all Django staff users (i.e., users that have access to the
Django admin site), thus allowing users to chat with any of your
helpdesk staff.

The optional components ``xmppserver.sessiondb`` and ``xmppserver.rosterdb``
also have their own hooks, which are installed automatically (with priority 1)
if you add them to your ``INSTALLED_APPS``.

Hook functions
--------------
.. automodule:: xmppserver.hooks
    :members:

.. _writing-hooks:

Writing hooks
-------------
Hooks are instantiated by XMPP streams when their functionality is needed.
For example, the authentication hook is instantiated when an XMPP client
is ready to authenticate. Each hook instance belongs to exactly one XMPP
stream, and is generally kept around until the stream is unbound
(disconnected).

Most hook methods are asynchronous, but the Django ORM is synchronous.
If you need to access the Django database from an asynchronous method,
you can write an ordinary synchronous method and use
:py:class:`channels.db.database_sync_to_async` on it, as explained in the
`Django Channels documentation <https://channels.readthedocs.io/en/latest/topics/databases.html>`_.

.. _authentication-hooks:

Authentication hooks
--------------------
.. autoflatclass:: xmppserver.hooks.base.BaseAuthHook
    :members:

.. _roster-hooks:

Roster hooks
------------
.. autoflatclass:: xmppserver.hooks.base.BaseRosterHook
    :members:

.. _session-hooks:

Session hooks
-------------
.. autoflatclass:: xmppserver.hooks.base.BaseSessionHook
    :members:
