"""XML report models backed by the XML node cache."""

import base64

from w3af.core.data.db.dbms import SQLiteDBMS
from w3af.core.data.db.exceptions import DBException
from w3af.core.data.db.history import HistoryItem, TraceReadException
from w3af.core.data.misc.dotdict import dotdict
from w3af.core.data.misc.encoding import smart_str_ignore
from w3af.plugins.output.xml_nodes import CachedXMLNode, XMLNode


class HTTPTransaction(CachedXMLNode):
    TEMPLATE = "http_transaction.tpl"

    def __init__(self, jinja2_env, _id, db: SQLiteDBMS):
        super().__init__(jinja2_env)
        self._id = _id
        self._db = db

    def get_cache_key(self):
        return f"http-transaction-{self._id}.data"

    def to_string(self):
        node = self.get_node_from_cache()
        if node is not None:
            return node

        request, response = HistoryItem(db=self._db).load_from_file(self._id)

        request_body = base64.encodebytes(
            smart_str_ignore(request.get_data() or "")
        ).decode("ascii")
        response_body = base64.encodebytes(
            smart_str_ignore(response.get_body() or "")
        ).decode("ascii")

        context = dotdict(
            {
                "id": self._id,
                "request": {
                    "status": request.get_request_line().strip(),
                    "headers": request.get_headers(),
                    "body": request_body,
                },
                "response": {
                    "status": response.get_status_line().strip(),
                    "headers": response.get_headers(),
                    "body": response_body,
                },
            }
        )

        transaction = self.get_template(self.TEMPLATE).render(context)
        self.save_node_to_cache(transaction)
        return transaction


class ScanInfo(CachedXMLNode):
    TEMPLATE = "scan_info.tpl"

    def __init__(self, jinja2_env, scan_target, plugins_dict, options_dict):
        super().__init__(jinja2_env)
        self._scan_target = scan_target
        self._plugins_dict = plugins_dict
        self._options_dict = options_dict

    def get_cache_key(self):
        return "scan-info.data"

    def to_string(self):
        node = self.get_node_from_cache()
        if node is not None:
            return node

        context = {
            "enabled_plugins": self._plugins_dict,
            "plugin_options": self._options_dict,
            "scan_target": self._scan_target,
        }
        transaction = self.get_template(self.TEMPLATE).render(context)
        self.save_node_to_cache(transaction)
        return transaction


class ScanStatus(XMLNode):
    TEMPLATE = "scan_status.tpl"

    def __init__(self, jinja2_env, status, total_urls, known_urls):
        super().__init__(jinja2_env)
        self._status = status
        self._total_urls = total_urls
        self._known_urls = known_urls

    def to_string(self):
        context = dotdict({})
        context.status = self._status["status"]
        context.is_paused = self._status["is_paused"]
        context.is_running = self._status["is_running"]
        context.active_crawl_plugin = self._status["active_plugin"]["crawl"]
        context.active_audit_plugin = self._status["active_plugin"]["audit"]
        context.current_crawl_request = self._status["current_request"]["crawl"]
        context.current_audit_request = self._status["current_request"]["audit"]
        context.crawl_input_speed = self._status["queues"]["crawl"]["input_speed"]
        context.crawl_output_speed = self._status["queues"]["crawl"]["output_speed"]
        context.crawl_queue_length = self._status["queues"]["crawl"]["length"]
        context.crawl_queue_processed_tasks = self._status["queues"]["crawl"][
            "processed_tasks"
        ]
        context.audit_input_speed = self._status["queues"]["audit"]["input_speed"]
        context.audit_output_speed = self._status["queues"]["audit"]["output_speed"]
        context.audit_queue_length = self._status["queues"]["audit"]["length"]
        context.audit_queue_processed_tasks = self._status["queues"]["audit"][
            "processed_tasks"
        ]
        context.grep_input_speed = self._status["queues"]["grep"]["input_speed"]
        context.grep_output_speed = self._status["queues"]["grep"]["output_speed"]
        context.grep_queue_length = self._status["queues"]["grep"]["length"]
        context.grep_queue_processed_tasks = self._status["queues"]["grep"][
            "processed_tasks"
        ]
        context.crawl_eta = self._status["eta"]["crawl"]
        context.audit_eta = self._status["eta"]["audit"]
        context.grep_eta = self._status["eta"]["grep"]
        context.all_eta = self._status["eta"]["all"]
        context.rpm = self._status["rpm"]
        context.sent_request_count = self._status["sent_request_count"]
        context.progress = self._status["progress"]
        context.total_urls = self._total_urls
        context.known_urls = self._known_urls

        return self.get_template(self.TEMPLATE).render(context)


class Finding(XMLNode):
    TEMPLATE = "finding.tpl"

    def __init__(self, jinja2_env, info, output, db: SQLiteDBMS):
        super().__init__(jinja2_env)
        self._info = info
        self._output = output
        self._db = db

    def to_string(self):
        info = self._info
        context = dotdict({})
        context.id_list = info.get_id()
        context.http_method = info.get_method()
        context.name = info.get_name()
        context.plugin_name = info.get_plugin_name()
        context.severity = info.get_severity()
        context.url = info.get_url().url_string if info.get_url() is not None else None
        context.var = info.get_token_name()
        context.description = info.get_desc(with_id=False)
        context.long_description = None

        if info.has_db_details():
            context.long_description = info.get_long_description()
            context.fix_guidance = info.get_fix_guidance()
            context.fix_effort = info.get_fix_effort()
            context.references = info.get_references()

        context.http_transactions = []
        for transaction in info.get_id():
            try:
                xml = HTTPTransaction(
                    self._jinja2_env,
                    transaction,
                    db=self._db,
                ).to_string()
            except (DBException, TraceReadException) as error:
                msg = (
                    'Failed to retrieve request with id %s from DB: "%s".'
                    ' The "%s" vulnerability will have an incomplete HTTP'
                    " transaction list."
                )
                self._output.error(msg % (transaction, error, context.name))
                continue

            context.http_transactions.append(xml)

        return self.get_template(self.TEMPLATE).render(context)
