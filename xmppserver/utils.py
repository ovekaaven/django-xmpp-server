from django.conf import settings as django_settings
import socket

def get_hostname_ipv4(hostname, allow_loopback):
    try:
        addrs = socket.gethostbyname_ex(hostname)[2]
        for ipv4 in addrs:
            if ipv4.startswith('127.') and not allow_loopback:
                continue
            return ipv4
    except:
        return None

def get_hostname_ipv6(hostname, allow_loopback):
    try:
        addrs = socket.getaddrinfo(hostname, None,
                                   family=socket.AF_INET6,
                                   type=socket.SOCK_DGRAM)
        for addr in addrs:
            ipv6 = addr[4][0]
            if ipv6 == '::1' and not allow_loopback:
                continue
            return ipv6
    except:
        return None

def get_network_ipv4():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    except:
        return None

def get_server_addr():
    hostname = socket.gethostname()
    if django_settings.DEBUG:
        # If we're on a development machine, chances are
        # it has a dynamic IP. To avoid surprises with that,
        # we'll permit using loopback, and also prefer IPv4,
        # since loopback setups tend to use IPv4 addresses.
        # For example, in end-user Ubuntu setups the hostname
        # maps to 127.0.1.1 by default.
        host = get_hostname_ipv4(hostname, True)
        if host:
            return host
        host = get_hostname_ipv6(hostname, True)
        if host:
            return host
    else:
        # If we're on a production server, we really
        # should get its unique address (not necessarily
        # public, just one that identifies the server).
        # We'll prefer its IPv6 address, if available
        # (it's more likely to be reasonably static).
        host = get_hostname_ipv6(hostname, False)
        if host:
            return host
        host = get_hostname_ipv4(hostname, False)
        if host:
            return host
        host = get_network_ipv4()
        if host:
            return host

    # If all else fails, fall back to just the hostname
    return hostname

def format_ipv6_addr(host, port):
    ipv4mapped = host.rsplit(':', 1)
    if ipv4mapped[0] == '::ffff':
        return "%s:%u" % (ipv4mapped[1], port)
    else:
        return "[%s]:%u" % (host, port)

def format_ipv4_addr(host, port):
    return "%s:%u" % (host, port)

def format_addr(host, port):
    if ':' in host:
        return format_ipv6_addr(host, port)
    else:
        return format_ipv4_addr(host, port)
