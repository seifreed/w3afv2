"""Build the resources owned by a scan core."""

from dataclasses import dataclass

from w3af.core.controllers.core_helpers.core_resource_lifecycle import (
    CoreResourceLifecycle,
)
from w3af.core.controllers.core_helpers.worker_pool_manager import WorkerPoolManager
from w3af.core.controllers.misc.dns_cache import DNSCache
from w3af.core.controllers.output_manager import create_output_manager
from w3af.core.controllers.output_manager.log_sink import LogSink
from w3af.core.controllers.output_manager.logging_bridge import configure_data_logging
from w3af.core.controllers.output_manager.manager import OutputManager
from w3af.core.controllers.parser_worker import get_parser_worker_bootstrap
from w3af.core.data.db.dbms import SQLiteDBMS, create_temp_db_instance
from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.misc.number_generator import NumberGenerator
from w3af.core.data.parsers.mp_document_parser import MultiProcessingDocumentParser
from w3af.core.data.parsers.parser_cache import ParserCache


@dataclass(frozen=True)
class CoreResources:
    """Resources and ownership information required by ``w3afCore``."""

    output_manager: OutputManager
    output: LogSink
    database: SQLiteDBMS
    owns_database: bool
    knowledge_base: DBKnowledgeBase
    dns_cache: DNSCache
    parser_cache: ParserCache
    id_generator: NumberGenerator
    worker_pool_manager: WorkerPoolManager
    resource_lifecycle: CoreResourceLifecycle


class CoreResourceFactory:
    """Create the infrastructure shared by the core and its scan."""

    def __init__(
        self, worker_threads: int, max_queued_tasks: int, max_tasks_per_child: int
    ) -> None:
        self._worker_threads = worker_threads
        self._max_queued_tasks = max_queued_tasks
        self._max_tasks_per_child = max_tasks_per_child

    def create(self, knowledge_base: DBKnowledgeBase | None = None) -> CoreResources:
        output_manager, output = create_output_manager()
        configure_data_logging(output)
        log_queue_provider, worker_initializer = get_parser_worker_bootstrap(
            output_manager
        )

        database, owns_database, knowledge_base = self._resolve_database(knowledge_base)
        dns_cache = DNSCache(output)
        parser_cache = ParserCache(
            mp_parser=MultiProcessingDocumentParser(
                log_queue_provider=log_queue_provider,
                worker_initializer=worker_initializer,
            ),
            db=database,
        )
        worker_pool_manager = WorkerPoolManager(
            output,
            self._worker_threads,
            self._max_queued_tasks,
            self._max_tasks_per_child,
        )
        resource_lifecycle = CoreResourceLifecycle(
            output_manager,
            dns_cache,
            parser_cache,
            database if owns_database else None,
            worker_pool_manager,
        )

        return CoreResources(
            output_manager,
            output,
            database,
            owns_database,
            knowledge_base,
            dns_cache,
            parser_cache,
            NumberGenerator(),
            worker_pool_manager,
            resource_lifecycle,
        )

    @staticmethod
    def _resolve_database(
        knowledge_base: DBKnowledgeBase | None,
    ) -> tuple[SQLiteDBMS, bool, DBKnowledgeBase]:
        if knowledge_base is None:
            database = create_temp_db_instance()
            return database, True, DBKnowledgeBase(db=database)

        knowledge_base.setup()
        return knowledge_base.db, False, knowledge_base
