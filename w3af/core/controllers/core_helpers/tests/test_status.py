# -*- coding: UTF-8 -*-
"""
test_status.py

Copyright 2012 Andres Riancho

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

import time
import unittest

import w3af.core.controllers.output_manager as om
from w3af.core.controllers.core_helpers.consumers.audit import audit
from w3af.core.controllers.core_helpers.consumers.crawl_infrastructure import (
    CrawlInfrastructure,
)
from w3af.core.controllers.core_helpers.consumers.grep import grep
from w3af.core.controllers.core_helpers.status import (
    AUDIT,
    CRAWL,
    GREP,
    PAUSED,
    RUNNING,
    STOPPED,
    Adjustment,
    CoreStatus,
)
from w3af.core.controllers.core_helpers.status_consumers import ConsumerMetrics
from w3af.core.controllers.w3af_core import w3afCore
from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.misc.number_generator import NumberGenerator
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest

QUEUED_ETA = 5 * 60.0


def fuzzable_request(path):
    return FuzzableRequest(URL(f"http://127.0.0.1{path}"))


class TestStatus(unittest.TestCase):

    def test_simple(self):
        core = w3afCore()
        self.addCleanup(core.worker_pool.terminate_join)
        s = CoreStatus(om.out, ConsumerMetrics(core.strategy, lambda: core.worker_pool))

        self.assertEqual(s.get_status(), STOPPED)

        self.assertFalse(s.is_running())
        s.start()
        self.assertTrue(s.is_running())

        s.set_current_fuzzable_request("crawl", "unittest_fr")
        s.set_running_plugin("crawl", "unittest_plugin")

        expected = "Crawling unittest_fr using crawl.unittest_plugin"
        self.assertEqual(s.get_status(), expected)

        s.pause(True)
        self.assertEqual(s.get_status(), PAUSED)

        s.pause(False)
        expected = "Crawling unittest_fr using crawl.unittest_plugin"
        self.assertEqual(s.get_status(), expected)

        s.set_current_fuzzable_request("audit", "unittest_fr_audit")
        s.set_running_plugin("audit", "unittest_plugin_audit")

        expected = (
            "Crawling unittest_fr using crawl.unittest_plugin\n"
            "Auditing unittest_fr_audit using audit.unittest_plugin_audit"
        )
        self.assertEqual(s.get_status(), expected)

        s.stop()
        self.assertEqual(s.get_status(), STOPPED)
        self.assertFalse(s.is_running())

    def test_has_started(self):
        s = CoreStatus(om.out)
        self.assertFalse(s.has_started())

        s.start()
        s.stop()
        self.assertTrue(s.has_started())

    def test_queue_status_not_started(self):
        core = w3afCore()
        s = CoreStatus(om.out, ConsumerMetrics(core.strategy, lambda: core.worker_pool))

        self.assertEqual(s.get_crawl_input_speed(), 0)
        self.assertEqual(s.get_crawl_output_speed(), 0)
        self.assertEqual(s.get_crawl_qsize(), 0)
        self.assertEqual(s.get_crawl_eta(), None)

        self.assertEqual(s.get_audit_input_speed(), 0)
        self.assertEqual(s.get_audit_output_speed(), 0)
        self.assertEqual(s.get_audit_qsize(), 0)
        self.assertEqual(s.get_audit_eta(), None)

        self.assertEqual(s.get_grep_eta(), None)

        core.worker_pool.terminate_join()

    def test_starting_scan_status(self):
        core = w3afCore()
        self.addCleanup(core.worker_pool.terminate_join)
        s = CoreStatus(om.out, ConsumerMetrics(core.strategy, lambda: core.worker_pool))
        s.start()

        self.assertEqual(s.get_status(), "Starting scan.")
        self.assertEqual(s.get_simplified_status(), RUNNING)

    def test_simplified_status(self):
        s = CoreStatus(om.out)
        self.assertEqual(s.get_simplified_status(), STOPPED)

        s.pause(True)
        self.assertTrue(s.is_paused())
        self.assertEqual(s.get_simplified_status(), PAUSED)

    def test_run_time_requires_start(self):
        s = CoreStatus(om.out)

        for method in (s.get_run_time, s.get_run_time_seconds, s.get_rpm):
            with self.assertRaisesRegex(RuntimeError, "before start"):
                method()

    def test_sent_request_count_is_local_to_the_status(self):
        generator = NumberGenerator()
        generator.inc()
        status = CoreStatus(om.out, id_generator=generator)

        generator.inc()

        self.assertEqual(status.get_sent_request_count(), 1)

    def test_run_time_after_start(self):
        s = CoreStatus(om.out)
        s.start()
        s._lifecycle.start_time_epoch -= 120

        self.assertGreaterEqual(s.get_run_time(), 2)
        self.assertGreaterEqual(s.get_run_time_seconds(), 120)
        self.assertEqual(s.get_scan_time().strip(), "2 minutes")
        self.assertEqual(
            s.get_rpm(), int(s.get_sent_request_count() / s.get_run_time())
        )
        self.assertEqual(s.get_sent_request_count(), 0)

    def test_scan_finished(self):
        s = CoreStatus(om.out, scans_completed=1)
        s.start()
        s.set_running_plugin("crawl", "web_spider")
        s.set_current_fuzzable_request("crawl", "fr")

        s.scan_finished()

        self.assertFalse(s.is_running())
        self.assertIsNone(s.get_running_plugin("crawl"))
        self.assertIsNone(s.get_current_fuzzable_request("crawl"))
        self.assertEqual(s.scans_completed, 2)

    def test_epoch_eta_to_string(self):
        s = CoreStatus(om.out)

        self.assertIsNone(s.epoch_eta_to_string(None))
        self.assertEqual(s.epoch_eta_to_string(61), "1 minute 1 second")


class TestCalculateETA(unittest.TestCase):

    def setUp(self):
        self.status = CoreStatus(om.out)
        self.status.start()

    def test_finished_consumer(self):
        self.assertEqual(self.status.calculate_eta(0, 0, 10, CRAWL), 0.0)

    def test_output_speed_zero(self):
        self.assertEqual(self.status.calculate_eta(10, 0, 10, CRAWL), QUEUED_ETA)

    def test_input_faster_than_output(self):
        adjustment = Adjustment(known=2.0, unknown=0.5, average=False)

        eta = self.status.calculate_eta(20, 10, 30, AUDIT, adjustment=adjustment)

        # t_queued = 30 / 10 * 2 = 6 ; t_new = 20 * 6 / 10 * 0.5 = 6
        self.assertEqual(eta, 12 * 60)

    def test_output_faster_than_input_is_averaged(self):
        adjustment = Adjustment(known=2.0)

        first_eta = self.status.calculate_eta(10, 20, 40, GREP, adjustment=adjustment)
        second_eta = self.status.calculate_eta(10, 20, 40, GREP, adjustment=adjustment)

        # t_queued = 40 / 20 = 2 ; t_new = 10 * 2 / 20 = 1 ; (2 + 1) * 2 = 6
        self.assertEqual(first_eta, 6 * 60 * 3 / 4)
        self.assertEqual(second_eta, 6 * 60 * 3 / 4 + first_eta / 4)


class TestStatusWithConsumers(unittest.TestCase):
    """
    Exercise the status using real (not started) consumers, the queue speeds
    and sizes are controlled by putting and getting items from their queues.
    """

    def setUp(self):
        self.core = w3afCore()
        self.addCleanup(self.core.worker_pool.terminate_join)
        self.status = CoreStatus(
            om.out,
            ConsumerMetrics(self.core.strategy, lambda: self.core.worker_pool),
        )
        self.status.start()

    def add_crawl(self):
        consumer = CrawlInfrastructure(
            [],
            self.core,
            0,
            knowledge_base=kb,
            output=om.out,
            configuration=self.core.configuration,
        )
        self.core.strategy._discovery_consumer = self.track(consumer)
        return consumer

    def add_audit(self):
        consumer = audit([], self.core, om.out, self.core.configuration)
        self.core.strategy._audit_consumer = self.track(consumer)
        return consumer

    def add_grep(self):
        private_ip = self.core.plugins.get_plugin_inst("grep", "private_ip")
        consumer = grep([private_ip], self.core, om.out, self.core.configuration)
        self.core.strategy._grep_consumer = self.track(consumer)
        return consumer

    def track(self, consumer):
        self.addCleanup(consumer.get_pool().terminate_join)
        self.addCleanup(self.core.strategy.set_consumers_to_none)
        return consumer

    def run_for(self, seconds):
        self.status._lifecycle.start_time_epoch = time.time() - seconds

    def test_queue_status(self):
        crawl = self.add_crawl()
        audit_consumer = self.add_audit()
        grep_consumer = self.add_grep()

        for consumer in (crawl, audit_consumer, grep_consumer):
            consumer.in_queue.put(fuzzable_request("/first"))
            consumer.in_queue.put(fuzzable_request("/second"))
            consumer.in_queue.get()
            consumer.in_queue.task_done()

        crawl._out_queue.put(fuzzable_request("/result"))

        for name in ("crawl", "audit", "grep"):
            self.assertEqual(getattr(self.status, f"get_{name}_qsize")(), 1)
            self.assertGreater(getattr(self.status, f"get_{name}_input_speed")(), 0)
            self.assertGreater(getattr(self.status, f"get_{name}_output_speed")(), 0)

        self.assertEqual(self.status.get_crawl_output_qsize(), 1)
        self.assertEqual(self.status.get_crawl_processed_tasks(), 0)
        self.assertEqual(self.status.get_audit_processed_tasks(), 1)
        self.assertEqual(self.status.get_grep_processed_tasks(), 1)
        self.assertFalse(self.status.has_finished_crawl())
        self.assertFalse(self.status.has_finished_audit())
        self.assertFalse(self.status.has_finished_grep())

    def test_queue_status_without_consumers(self):
        self.assertEqual(self.status.get_crawl_output_qsize(), 0)
        self.assertEqual(self.status.get_crawl_processed_tasks(), 0)
        self.assertEqual(self.status.get_audit_processed_tasks(), 0)
        self.assertIsNone(self.status.get_grep_processed_tasks())
        self.assertEqual(self.status.get_grep_qsize(), 0)
        self.assertEqual(self.status.get_grep_input_speed(), 0)
        self.assertEqual(self.status.get_grep_output_speed(), 0)
        self.assertEqual(self.status.get_core_worker_pool_queue_size(), 0)

    def test_eta_without_consumers(self):
        self.assertEqual(self.status.get_eta(), 0)
        self.assertEqual(self.status.get_crawl_eta(), 0.0)
        self.assertEqual(self.status.get_audit_eta(), 0.0)
        self.assertEqual(self.status.get_grep_eta(), 0.0)
        self.assertFalse(self.status.any_consumer_running())

    def test_eta_only_grep_running(self):
        self.add_grep().in_queue.put("response")

        self.assertEqual(self.status.get_eta(), QUEUED_ETA)

    def test_eta_crawl_finished_grep_slower_than_audit(self):
        self.add_audit()
        self.add_grep().in_queue.put("response")

        self.assertEqual(self.status.get_eta(), QUEUED_ETA * 0.1)

    def test_eta_crawl_finished_audit_slower_than_grep(self):
        self.add_audit().in_queue.put("request")
        self.add_grep()

        self.assertEqual(self.status.get_eta(), QUEUED_ETA)

    def test_eta_all_phases_audit_and_grep_after_crawl(self):
        self.add_crawl()
        self.add_audit().in_queue.put("request")
        self.add_grep().in_queue.put("response")

        expected = QUEUED_ETA * 0.75 + QUEUED_ETA * 0.05
        self.assertEqual(self.status.get_eta(), expected)

    def test_eta_all_phases_crawl_is_the_slowest(self):
        self.add_crawl().in_queue.put(fuzzable_request("/"))
        self.add_audit().in_queue.put("request")
        self.add_grep()

        self.assertEqual(self.status.get_eta(), QUEUED_ETA)

    def test_progress_while_consumers_run(self):
        self.add_crawl()
        self.run_for(10)

        self.assertEqual(self.status.get_progress_percentage(eta=0), 99)
        self.assertEqual(self.status.get_progress_percentage(eta=10), 50)

    def test_progress_when_everything_finished(self):
        self.run_for(10)

        self.assertEqual(self.status.get_progress_percentage(), 100)

    def test_any_consumer_running(self):
        audit_consumer = self.add_audit()
        self.assertTrue(self.status.any_consumer_running())

        audit_consumer.set_has_finished()
        grep_consumer = self.add_grep()
        self.assertTrue(self.status.any_consumer_running())

        grep_consumer.set_has_finished()
        self.assertFalse(self.status.any_consumer_running())

    def assertAdjustment(self, adjustment, known, unknown, average=True):
        self.assertEqual(
            (adjustment.known, adjustment.unknown, adjustment.average),
            (known, unknown, average),
        )

    def test_crawl_adjustment_ratio(self):
        expected = {10: (0.5, 7.5), 90: (0.75, 4.0), 200: (0.75, 0.75)}

        for run_time, (known, unknown) in expected.items():
            self.run_for(run_time)
            ratio = self.status.get_crawl_adjustment_ratio()
            self.assertAdjustment(ratio, known, unknown)

    def test_audit_adjustment_ratio(self):
        self.assertAdjustment(self.status.get_audit_adjustment_ratio(), 1.2, 0)

        self.add_crawl()
        expected = {10: (1, 3.0), 90: (1, 2.0), 200: (1.1, 2.0)}

        for run_time, (known, unknown) in expected.items():
            self.run_for(run_time)
            ratio = self.status.get_audit_adjustment_ratio()
            self.assertAdjustment(ratio, known, unknown)

    def test_grep_adjustment_ratio(self):
        self.assertAdjustment(
            self.status.get_grep_adjustment_ratio(), 1.0, 0, average=False
        )

        crawl = self.add_crawl()
        expected = {10: 40, 45: 20, 90: 10, 150: 7.5, 200: 0.5}

        for run_time, unknown in expected.items():
            self.run_for(run_time)
            ratio = self.status.get_grep_adjustment_ratio()
            self.assertEqual(ratio.unknown, unknown)

        self.add_audit()
        self.assertAdjustment(self.status.get_grep_adjustment_ratio(), 1.0, 0.75)

        crawl.set_has_finished()
        self.assertAdjustment(
            self.status.get_grep_adjustment_ratio(), 1.0, 0.5, average=False
        )

    def test_status_as_dict(self):
        self.add_crawl().in_queue.put(fuzzable_request("/"))
        self.status.set_running_plugin("crawl", "web_spider")
        self.status.set_current_fuzzable_request("crawl", fuzzable_request("/"))
        self.run_for(60)

        data = self.status.get_status_as_dict()

        self.assertEqual(data["status"], RUNNING)
        self.assertFalse(data["is_paused"])
        self.assertTrue(data["is_running"])
        self.assertEqual(data["active_plugin"], {"crawl": "web_spider", "audit": None})
        self.assertEqual(
            data["current_request"],
            {"crawl": "GET http://127.0.0.1/", "audit": None},
        )
        self.assertEqual(data["queues"]["crawl"]["length"], 1)
        self.assertEqual(data["queues"]["audit"]["length"], 0)
        self.assertIsNone(data["queues"]["grep"]["processed_tasks"])
        self.assertEqual(data["eta"]["crawl"].strip(), "5 minutes")
        self.assertEqual(data["eta"]["all"], "0 seconds")
        self.assertEqual(data["progress"], 99)
        self.assertEqual(data["rpm"], self.status.get_rpm())
        self.assertEqual(
            data["sent_request_count"], self.status.get_sent_request_count()
        )

    def test_long_status_when_stopped(self):
        self.status.stop()

        self.assertEqual(self.status.get_long_status(), STOPPED)

    def test_long_status_while_running(self):
        self.add_crawl()
        self.add_grep().in_queue.put("response")
        self.run_for(60)

        long_status = self.status.get_long_status()

        self.assertIn("Starting scan.\nCrawl phase: In (0.00 URLs/min)", long_status)
        self.assertIn("Grep phase: In (0.10 URLs/min)", long_status)
        self.assertIn("Pending (1 URLs) ETA (5 minutes", long_status)
        self.assertIn("Overall scan progress: ", long_status)
        self.assertIn("Time to complete scan: ", long_status)


kb = DBKnowledgeBase()
