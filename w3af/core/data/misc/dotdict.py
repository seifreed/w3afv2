from typing import Any

from w3af.core.data.misc.encoding import smart_unicode


class dotdict(dict):
    """dot.notation access to dictionary attributes"""

    def __setattr__(self, key, value):
        """
        Overriding in order to translate every value to an unicode object

        :param key: The attribute name to set
        :param value: The value (string, unicode or anything else)
        :return: None
        """
        if isinstance(value, str):
            value = smart_unicode(value)

        self[key] = value

    def __getattr__(self, key: str) -> Any:
        return self.get(key)

    __delattr__ = dict.__delitem__
