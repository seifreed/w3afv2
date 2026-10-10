"""
plugins.py

Copyright 2006 Andres Riancho

This file is part of w3af, http://w3af.org/ .

w3af is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 2 of the License.

w3af is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with w3af; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

"""

import os
from functools import partial

from w3af import ROOT_PATH
from w3af.core.controllers.core_helpers.plugin_catalog import PluginCatalog
from w3af.core.controllers.core_helpers.plugin_dependency_resolver import (
    PluginDependencyResolver,
)
from w3af.core.controllers.core_helpers.plugin_instance_factory import (
    PluginInstanceFactory,
)


class CorePlugins(PluginCatalog):

    def __init__(self, w3af_core, output, output_manager):
        self._w3af_core = w3af_core
        self._output = output
        self._output_manager = output_manager
        self._plugin_instance_factory = PluginInstanceFactory(w3af_core, output)

        self.initialized = False
        self._plugins_names_dict = None
        self._plugins_options = None
        self.plugins = None
        self.zero_enabled_plugins()

    def zero_enabled_plugins(self):
        """
        Init some internal variables; this method is called when the whole
        process starts, and when the user loads a new profile.
        """
        plugin_types = self.get_plugin_types()
        self._plugins_names_dict = {plugin_type: [] for plugin_type in plugin_types}
        self._plugins_options = {plugin_type: {} for plugin_type in plugin_types}
        self._plugins_options["attack"] = {}
        self.plugins = {plugin_type: [] for plugin_type in plugin_types}

        # After we zero all options and enabled plugins we need to call
        # init_plugins again
        self.initialized = False

    def init_plugins(self):
        """
        The user interfaces should run this method *before* calling start().
        If they don't do it, an exception is raised.
        """
        # This is inited before all, to have a full logging support.
        self._output_manager.set_output_plugins(self._plugins_names_dict["output"])

        # Create an instance of each requested plugin and add it to the plugin
        # list. Plugins are added taking care of plugin dependencies and
        # configuration
        #
        # Create all the plugin instances
        #
        self.plugin_factory()

        #
        # Some extra init steps for mangle plugins
        #
        mangle = self.plugins["mangle"]
        self._w3af_core.uri_opener.settings.set_mangle_plugins(mangle)

        # The plugin factory might raise an exception due to invalid plugin
        # configurations. Only set the initialized attribute if we get to the
        # end of init_plugins()
        self.initialized = True

    def set_plugin_options(self, plugin_type, plugin_name, plugin_options):
        """
        :param plugin_type: The plugin type, like 'audit' or 'crawl'
        :param plugin_name: The plugin name, like 'sqli' or 'web_spider'
        :param plugin_options: An OptionList with the option objects for a
                               plugin.

        :return: No value is returned.
        """
        if plugin_type.lower() == "output":
            self._output_manager.set_plugin_options(plugin_name, plugin_options)

        # Save the options, even if they are invalid. This is a good idea
        # because:
        #
        #   * If the user sees an error raised by the set_options() below he'll
        #     fix the configuration (calling this method again) and override
        #     the invalid settings
        #
        #   * If the user ignores the error raised by set_options() and tries
        #     to start the scan init_plugins will fail, this is:
        #     https://github.com/andresriancho/w3af/issues/7477
        #
        self._plugins_options[plugin_type][plugin_name] = plugin_options

        # The following lines make sure that the plugin will accept the options
        # that the user is setting
        plugin_inst = self.get_plugin_inst(plugin_type, plugin_name)
        plugin_inst.set_options(plugin_options)

    def get_plugin_options(self, plugin_type, plugin_name):
        """
        Get the options for a plugin.

        IMPORTANT NOTE: This method only returns the options for a plugin
        that was previously configured using set_plugin_options. If you want
        to get the default options for a plugin, get a plugin instance and
        perform a plugin.get_options()

        :return: An OptionList with the plugin options.
        """
        return self._plugins_options.get(plugin_type, {}).get(plugin_name, None)

    def get_all_plugin_options(self):
        return self._plugins_options

    def get_all_enabled_plugins(self):
        return self._plugins_names_dict

    def get_enabled_plugins(self, plugin_type):
        return self._plugins_names_dict[plugin_type]

    def set_plugins(self, plugin_names, plugin_type, raise_on_error=True):
        """
        This method sets the plugins that w3afCore is going to use. Before this
        plugin existed w3afCore used setcrawl_plugins() / setAuditPlugins() /
        etc , this wasn't really extensible and was replaced with a combination
        of set_plugins and get_plugin_types. This way the user interface isn't
        bound to changes in the plugin types that are added or removed.

        :param plugin_names: A list with the names of the Plugins that will be
                             run.
         :param plugin_type: The type of the plugin.

        :return: A list of plugins that are unknown to the framework. This is
                 mainly used to have some error handling related to old profiles
                 that might reference deprecated plugins.
        """
        # Validate the input...
        plugin_names = list(dict.fromkeys(plugin_names))
        known_plugin_names = self.get_plugin_list(plugin_type)
        unknown_plugins = []

        for plugin_name in plugin_names:
            if (
                plugin_name not in known_plugin_names
                and plugin_name.replace("!", "") not in known_plugin_names
                and plugin_name != "all"
            ):

                if raise_on_error:
                    raise ValueError(f"Unknown plugin {plugin_name}")
                else:
                    unknown_plugins.append(plugin_name)

        # If we don't raise an error when an unknown plugin name is enabled,
        # at least don't try to call the "_set_plugin_generic" method with it
        plugin_names = [pn for pn in plugin_names if pn not in unknown_plugins]

        set_dict = {
            "crawl": partial(self._set_plugin_generic, "crawl"),
            "audit": partial(self._set_plugin_generic, "audit"),
            "grep": partial(self._set_plugin_generic, "grep"),
            "output": partial(self._set_plugin_generic, "output"),
            "mangle": partial(self._set_plugin_generic, "mangle"),
            "bruteforce": partial(self._set_plugin_generic, "bruteforce"),
            "auth": partial(self._set_plugin_generic, "auth"),
            "infrastructure": partial(self._set_plugin_generic, "infrastructure"),
            "evasion": self._set_evasion_plugins,
        }

        set_dict[plugin_type](plugin_names)

        return unknown_plugins

    def get_plugin_inst(self, plugin_type, plugin_name):
        """
        :return: An instance of a plugin.
        """
        custom_options = self._plugins_options[plugin_type].get(plugin_name)
        plugin_inst = self._plugin_instance_factory.create(
            plugin_type, plugin_name, custom_options
        )

        # This will init some plugins like mangle and output
        if plugin_type == "attack" and not self.initialized:
            self.init_plugins()

        return plugin_inst

    def expand_all(self):
        for plugin_type, enabled_plugins in self._plugins_names_dict.items():
            if "all" in enabled_plugins:
                file_list = [
                    f
                    for f in os.listdir(os.path.join(ROOT_PATH, "plugins", plugin_type))
                ]
                all_plugins = [
                    os.path.splitext(f)[0]
                    for f in file_list
                    if os.path.splitext(f)[1] == ".py"
                ]
                all_plugins.remove("__init__")

                enabled_plugins.extend(all_plugins)
                enabled_plugins = list(set(enabled_plugins))
                enabled_plugins.remove("all")
                self._plugins_names_dict[plugin_type] = enabled_plugins

    def remove_exclusions(self):
        for enabled_plugins in self._plugins_names_dict.values():
            for plugin_name in enabled_plugins[:]:
                if plugin_name.startswith("!"):
                    enabled_plugins.remove(plugin_name)
                    enabled_plugins.remove(plugin_name.replace("!", ""))

    def create_instances(self):
        for plugin_type, enabled_plugins in self._plugins_names_dict.items():
            for plugin_name in enabled_plugins:
                plugin_instance = self.get_plugin_inst(plugin_type, plugin_name)
                if plugin_instance not in self.plugins[plugin_type]:
                    self.plugins[plugin_type].append(plugin_instance)
                else:
                    # Ensure that the latest settings are applied to the instance
                    # that will be used for execution
                    for existing_inst in self.plugins[plugin_type]:
                        if (
                            existing_inst.get_name() == plugin_name
                            and plugin_name
                            in list(self._plugins_options[plugin_type].keys())
                        ):
                            custom_options = self._plugins_options[plugin_type][
                                plugin_name
                            ]
                            existing_inst.set_options(custom_options)

    def plugin_factory(self):
        """
        This method creates the user requested plugins.

        :return: A list with plugins to be executed, this list is ordered using
                 the exec priority.
        """
        self.expand_all()
        self.remove_exclusions()
        resolver = PluginDependencyResolver(
            self._plugins_names_dict,
            self.get_quick_instance,
            self._output.information,
        )
        resolver.resolve()

        # Now the self._plugins_names_dict has all the plugin names that
        # we should enable, for all types, but in the incorrect order:
        # without taking care of dependencies
        resolver.order()
        self.create_instances()

    def _set_plugin_generic(self, plugin_type, plugin_list):
        """
        :param plugin_type: The plugin type where to store the @plugin_list.
        :param plugin_list: A list with the names of @plugin_type plugins to be
                            run.
        """
        self._plugins_names_dict[plugin_type] = plugin_list

    def _set_evasion_plugins(self, evasion_plugins):
        """
        :param evasion_plugins: A list with the names of Evasion Plugins that
                                will be used.
        :return: No value is returned.
        """
        self._plugins_names_dict["evasion"] = evasion_plugins
        self.plugin_factory()

        self._w3af_core.uri_opener.set_evasion_plugins(self.plugins["evasion"])
