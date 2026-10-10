"""
ETA adjustment rules for scan phases.
"""

from operator import xor

from w3af.core.controllers.core_helpers.status_eta import Adjustment


def get_crawl_adjustment(run_time):
    if run_time < 60:
        return Adjustment(known=0.5, unknown=7.5)

    if run_time < 120:
        return Adjustment(known=0.75, unknown=4.0)

    return Adjustment(known=0.75, unknown=0.75)


def get_audit_adjustment(run_time, crawl_finished):
    if crawl_finished:
        return Adjustment(known=1.2, unknown=0)

    if run_time < 60:
        return Adjustment(known=1, unknown=3.0)

    if run_time < 120:
        return Adjustment(known=1, unknown=2.0)

    return Adjustment(known=1.1, unknown=2.0)


def get_grep_adjustment(run_time, crawl_finished, audit_finished):
    if crawl_finished and audit_finished:
        return Adjustment(known=1.0, unknown=0, average=False)

    if run_time < 30:
        return Adjustment(known=1.0, unknown=40)

    if run_time < 60:
        return Adjustment(known=1.0, unknown=20)

    if run_time < 120:
        return Adjustment(known=1.0, unknown=10)

    if run_time < 180:
        return Adjustment(known=1.0, unknown=7.5)

    if xor(crawl_finished, audit_finished):
        return Adjustment(known=1.0, unknown=0.5, average=False)

    return Adjustment(known=1.0, unknown=0.75)
