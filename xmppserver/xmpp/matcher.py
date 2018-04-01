from slixmpp import StanzaPath

def is_server_stanza(stanza):
    target = stanza['to']
    if target.user != '':
        return False
    if target.domain != '' and \
       target.domain != stanza.stream.host:
        return False
    return True

def is_local_stanza(stanza):
    target = stanza['to']
    if target.user != '' and target.resource != '':
        return False
    if target.domain != '' and \
       target.domain != stanza.stream.host:
        return False
    return True

class ServerStanzaPath(StanzaPath):
    def match(self, stanza):
        if not StanzaPath.match(self, stanza):
            return False
        return is_server_stanza(stanza)

class LocalStanzaPath(StanzaPath):
    def match(self, stanza):
        if not StanzaPath.match(self, stanza):
            return False
        return is_local_stanza(stanza)

class RemoteStanzaPath(StanzaPath):
    def match(self, stanza):
        if not StanzaPath.match(self, stanza):
            return False
        return not is_local_stanza(stanza)
