from w3af.core.data.misc.serialize import HIGHEST_PROTOCOL, dumps


def cpickle_dumps(obj):
    """
    pickle doesn't handle dict sub-classes when using HIGHEST_PROTOCOL, so
    we do some checks here to avoid bugs.

    We pickle using HIGHEST_PROTOCOL if obj is not a dict subclass, otherwise we
    just use protocol version 1.

    :see: http://bugs.python.org/issue826897
    :param obj: The object to pickle
    :return: The pickled version of obj
    """
    if isinstance(obj, dict):
        return dumps(obj, 1)

    return dumps(obj, HIGHEST_PROTOCOL)
