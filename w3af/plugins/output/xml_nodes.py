"""Cached XML node primitives used by the XML output plugin."""

import os

import lz4.frame

from w3af.core.filesystem import get_temp_dir


class FindingsCache:
    """Store rendered finding fragments outside the process heap."""

    COMPRESSION_LEVEL = 2

    @staticmethod
    def create_cache_path():
        cache_path = FindingsCache.get_cache_path()

        if not os.path.exists(cache_path):
            os.makedirs(cache_path)

    @staticmethod
    def get_cache_path():
        return os.path.join(get_temp_dir(), "xml_file", "findings")

    def get_filename_from_uniq_id(self, uniq_id):
        return os.path.join(FindingsCache.get_cache_path(), uniq_id)

    def get_node_from_cache(self, uniq_id):
        filename = self.get_filename_from_uniq_id(uniq_id)

        try:
            with open(filename, "rb") as cache_fh:
                node = lz4.frame.decompress(cache_fh.read())
        except (OSError, RuntimeError):
            return None

        return node.decode("utf-8")

    def save_finding_to_cache(self, uniq_id, node):
        filename = self.get_filename_from_uniq_id(uniq_id)
        node = node.encode("utf-8")
        with open(filename, "wb") as cache_fh:
            cache_fh.write(lz4.frame.compress(node))

    def evict_from_cache(self, uniq_id):
        filename = self.get_filename_from_uniq_id(uniq_id)

        if os.path.exists(filename):
            os.remove(filename)

    def list(self):
        return os.listdir(FindingsCache.get_cache_path())


class XMLNode:
    """Render an XML template using a shared Jinja environment."""

    TEMPLATE: str | None = None
    TEMPLATE_INST = None

    def __init__(self, jinja2_env):
        self._jinja2_env = jinja2_env

    def get_template(self, template_name):
        return self._jinja2_env.get_template(template_name)


class CachedXMLNode(XMLNode):
    """Base node that persists rendered XML fragments in the temp directory."""

    COMPRESSION_LEVEL = 2

    @staticmethod
    def create_cache_path():
        cache_path = CachedXMLNode.get_cache_path()

        if not os.path.exists(cache_path):
            os.makedirs(cache_path)

    @staticmethod
    def get_cache_path():
        return os.path.join(get_temp_dir(), "xml_file")

    def get_cache_key(self):
        raise NotImplementedError

    def get_filename(self):
        return os.path.join(CachedXMLNode.get_cache_path(), self.get_cache_key())

    def get_node_from_cache(self):
        filename = self.get_filename()

        try:
            with open(filename, "rb") as cache_fh:
                node = lz4.frame.decompress(cache_fh.read())
        except (OSError, RuntimeError):
            return None

        return node.decode("utf-8")

    def save_node_to_cache(self, node):
        filename = self.get_filename()
        node = node.encode("utf-8")
        with open(filename, "wb") as cache_fh:
            cache_fh.write(lz4.frame.compress(node))
