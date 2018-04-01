from slixmpp.exceptions import XMPPError
from ..conf import settings

mechanisms = {}

def sasl_mech():
    def register(mech):
        mechanisms[mech.name] = mech
        return mech
    return register

class Mechanism(object):
    name = None

    def __init__(self, auth):
        self.auth = auth

    @staticmethod
    async def available(auth):
        return True

    @property
    def stream(self):
        return self.auth.stream

    @property
    def boundjid(self):
        return self.auth.stream.boundjid

    async def challenge(self, data=None):
        return await self.auth._async_challenge(data)

    def process(self, request):
        raise NotImplementedError()

class LegacyAuth(Mechanism):
    name = 'xep_0078'

    @staticmethod
    async def available(auth):
        return settings.ALLOW_LEGACY_AUTH

    async def process(self, request):
        if 'username' not in request or \
           'resource' not in request:
            raise XMPPError('not-acceptable')
        username = request['username']
        if not await self.auth.check_password(username,
                                              request.get('password', '')):
            raise XMPPError('not-authorized')
        self.boundjid.user = username
        self.boundjid.resource = request['resource']

@sasl_mech()
class Anonymous(Mechanism):
    name = 'ANONYMOUS'

    @staticmethod
    async def available(auth):
        if settings.ALLOW_ANONYMOUS_LOGIN:
            return True
        else:
            return False

    async def process(self, request):
        if settings.ALLOW_ANONYMOUS_LOGIN:
            username = self.auth.generate_anonymous_user()
        else:
            raise XMPPError('not-authorized')
        self.boundjid.user = username

@sasl_mech()
class External(Mechanism):
    name = 'EXTERNAL'

    @staticmethod
    async def available(auth):
        # check client certificate, if available
        cert = auth.stream.get_client_cert()
        if not cert:
            return False
        # TODO: handle client certificates
        return False

    async def process(self, request):
        pass

@sasl_mech()
class Plain(Mechanism):
    name = 'PLAIN'

    async def process(self, request):
        if request.xml.text:
            value = request['value']
        else:
            value = await self.challenge()
        toks = value.split(b'\0')
        if len(toks) != 3:
            raise XMPPError('malformed-request')
        toks = [x.decode('utf8') for x in toks]
        username = toks[1]
        if not await self.auth.check_password(username,
                                              toks[2]):
            raise XMPPError('not-authorized')
        authcid = "%s@%s" % (username, self.stream.host)
        if toks[0] != '' and toks[0] != authcid:
            # authzid not supported yet
            raise XMPPError('invalid-authzid')
        self.boundjid.user = username

def get_sasl_by_name(name):
    return mechanisms.get(name, None)

async def get_sasl_available(stream):
    return [m for m in mechanisms.values() if await m.available(stream)]
