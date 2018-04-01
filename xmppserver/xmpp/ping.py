class Ping(object):
    def __init__(self, stream):
        stream.whitespace_keepalive = stream.whitespace_keepalives
        stream.register_plugin('xep_0199')
        # TODO: implement ping keepalives that work for servers

