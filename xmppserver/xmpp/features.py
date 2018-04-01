from slixmpp.stanza import StreamFeatures

class Features(object):
    def __init__(self, stream):
        self.features = set()
        self.feature_handlers = {}

        # slixmpp will want to call stream.register_feature
        stream.register_feature = self.register_feature
        stream.unregister_feature = self.unregister_feature

    # slixmpp will want to use stream.features as a set
    def add(self, name):
        return self.features.add(name)
    def remove(self, name):
        return self.features.remove(name)
    def __contains__(self, item):
        return item in self.features
    def __iter__(self):
        return iter(self.features)

    async def get_features(self):
        features = StreamFeatures()
        for feature in self.feature_handlers.keys():
            # initializing plugins autocreates the elements
            features._get_plugin(feature)

        # RFC 3921 session creation is obsolete
        features['session']._set_sub_text('optional', keep=True)

        return features

    def register_feature(self, name, handler, restart=False, order=5000):
        if name == 'mechanisms' or name == 'auth':
            return
        # these handlers are designed for client-side operation,
        # so we can't use them most of the time, but we can
        # register them anyway, if only to put their names
        # into the stream feature list
        self.feature_handlers[name] = (handler, restart)

    def unregister_feature(self, name, order):
        if name in self.feature_handlers:
            del self.feature_handlers[name]

