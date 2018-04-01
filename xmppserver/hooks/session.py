from .base import BaseSessionHook

class DefaultSessionHook(BaseSessionHook):

    # Since I don't want to define any models in the main xmppserver
    # module, the default session hook isn't doing much. For proper
    # session support, the xmppserver.sessiondb app should be added.

    async def bind(self, stream):
        return True

    async def get_preferred_resource(self, username):
        return '' # broadcast to all resources

    async def get_resource(self, jid):
        return 0 # all resources are available
