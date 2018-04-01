from .auth import DefaultAuthHook
from .roster import DefaultRosterHook
from .session import DefaultSessionHook

hooks = {
    'auth': DefaultAuthHook,
    'roster': DefaultRosterHook,
    'session': DefaultSessionHook,
}
hook_priorities = {}

def set_hook(type, hook, priority=1000):
    """
    Install new hook. Hooks are only installed if their
    priority is higher than the previously installed hook.
    The default hooks have priority 0.

    :param str type: Hook type (either 'auth', 'roster', or 'session')
    :param hook: Hook class
    :param priority: Hook priority
    """
    old_priority = hook_priorities.get(type, 0)
    if priority > old_priority:
        hooks[type] = hook
        hook_priorities[type] = priority

def get_hook(type):
    """
    Get current hook.

    :param str type: Hook type
    :return: Hook class
    """
    return hooks.get(type)
