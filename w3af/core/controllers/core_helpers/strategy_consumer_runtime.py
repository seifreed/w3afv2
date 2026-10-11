"""Manage the consumers that participate in a scan strategy."""

import time

from w3af.core.controllers.core_helpers.consumers.audit import audit
from w3af.core.controllers.core_helpers.consumers.auth import auth
from w3af.core.controllers.core_helpers.consumers.bruteforce import bruteforce
from w3af.core.controllers.core_helpers.consumers.crawl_infrastructure import (
    CrawlInfrastructure,
)
from w3af.core.controllers.core_helpers.consumers.grep import grep
from w3af.core.controllers.core_helpers.consumers.seed import seed


class StrategyConsumerRuntime:
    """Create, operate, and release strategy consumers."""

    def __init__(self, scan_context, knowledge_base, output, configuration):
        self._scan_context = scan_context
        self._knowledge_base = knowledge_base
        self._output = output
        self._configuration = configuration
        self.reset()

    def reset(self):
        self._grep_consumer = None
        self._audit_consumer = None
        self._auth_consumer = None
        self._discovery_consumer = None
        self._bruteforce_consumer = None
        self._seed_producer = seed(
            self._scan_context, self._knowledge_base, self._output
        )

    def get_grep_consumer(self):
        return self._grep_consumer

    def get_audit_consumer(self):
        return self._audit_consumer

    def get_discovery_consumer(self):
        return self._discovery_consumer

    def get_bruteforce_consumer(self):
        return self._bruteforce_consumer

    def get_auth_consumer(self):
        return self._auth_consumer

    def get_seed_producer(self):
        return self._seed_producer

    def setup_crawl_infrastructure(self):
        crawl_plugins = self._scan_context.plugins.get_plugin_instances("crawl")
        infrastructure_plugins = self._scan_context.plugins.get_plugin_instances(
            "infrastructure"
        )

        if crawl_plugins or infrastructure_plugins:
            discovery_plugins = infrastructure_plugins + crawl_plugins
            self._discovery_consumer = CrawlInfrastructure(
                discovery_plugins,
                self._scan_context,
                self._configuration.get("max_discovery_time"),
                knowledge_base=self._knowledge_base,
                output=self._output,
                configuration=self._configuration,
            )
            self._discovery_consumer.start()

    def setup_grep(self):
        grep_plugins = self._scan_context.plugins.get_plugin_instances("grep")

        if grep_plugins:
            self._grep_consumer = grep(
                grep_plugins,
                self._scan_context,
                output=self._output,
                configuration=self._configuration,
            )
            self._scan_context.uri_opener.set_grep_queue_put(self._grep_consumer.grep)
            self._grep_consumer.start()

    def setup_audit(self):
        self._output.debug("Called _setup_audit()")
        audit_plugins = self._scan_context.plugins.get_plugin_instances("audit")

        if audit_plugins:
            self._audit_consumer = audit(
                audit_plugins,
                self._scan_context,
                output=self._output,
                configuration=self._configuration,
            )
            self._audit_consumer.start()

    def setup_bruteforce(self):
        bruteforce_plugins = self._scan_context.plugins.get_plugin_instances(
            "bruteforce"
        )

        if bruteforce_plugins:
            self._bruteforce_consumer = bruteforce(
                bruteforce_plugins, self._scan_context, output=self._output
            )
            self._bruteforce_consumer.start()

    def setup_auth(self, timeout=5):
        auth_plugins = self._scan_context.plugins.get_plugin_instances("auth")

        if auth_plugins:
            self._auth_consumer = auth(
                auth_plugins, self._scan_context, timeout, output=self._output
            )
            self._auth_consumer.start()
            self._auth_consumer.force_login()

    def seed_discovery(self):
        self._seed_producer.seed_output_queue(self._configuration.get("targets"))

    def terminate(self):
        """Terminate every active consumer and clear its reference."""
        for consumer_name in ("discovery", "audit", "auth", "bruteforce", "grep"):
            consumer = getattr(self, f"_{consumer_name}_consumer")
            if consumer is None:
                msg = "%s consumer is None. Skipping call to terminate()"
                self._output.debug(msg % consumer_name)
                continue

            self._output.debug(f"Calling terminate() on {consumer_name} consumer")
            start = time.time()
            setattr(self, f"_{consumer_name}_consumer", None)
            consumer.terminate()
            spent = time.time() - start
            self._output.debug(
                f"terminate() on {consumer_name} consumer took {spent:.2f} seconds"
            )

    def teardown_grep(self):
        self._output.debug("Called strategy._teardown_grep()")
        if self._grep_consumer is not None:
            self._grep_consumer.join()
            self._grep_consumer = None

    def teardown_audit(self):
        self._output.debug("Called strategy._teardown_audit()")
        if self._audit_consumer is not None:
            self._audit_consumer.join()
            self._audit_consumer = None

    def teardown_auth(self):
        self._output.debug("Called strategy._teardown_auth()")
        if self._auth_consumer is not None:
            self._auth_consumer.join()
            self._auth_consumer = None

    def teardown_bruteforce(self):
        self._output.debug("Called strategy._teardown_bruteforce()")
        if self._bruteforce_consumer is not None:
            self._bruteforce_consumer.join()
            self._bruteforce_consumer = None

    def teardown_crawl_infrastructure(self):
        self._output.debug("Called strategy._teardown_crawl_infrastructure()")
        if self._discovery_consumer is not None:
            self._discovery_consumer.join()
            self._scan_context.plugins.set_plugin_instances("crawl", [])
            self._scan_context.plugins.set_plugin_instances("infrastructure", [])
            self._discovery_consumer = None

    def clear_queue_speed_data(self):
        consumers = [
            self._grep_consumer,
            self._audit_consumer,
            self._discovery_consumer,
            self._bruteforce_consumer,
        ]
        for consumer in (item for item in consumers if item is not None):
            consumer.in_queue.clear()
