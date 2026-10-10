"""
parser_worker.py

Copyright 2024 Andres Riancho

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

from functools import partial

from w3af.core.controllers.output_manager.log_sink import LogSink
from w3af.core.controllers.output_manager.logging_bridge import configure_data_logging
from w3af.core.controllers.profiling import start_profiling_no_core
from w3af.core.data.parsers.mp_document_parser import configure_multiprocessing


def get_parser_log_queue(output_manager):
    """
    :return: The output manager input queue that parser worker processes write
             their log records to.
    """
    if not output_manager.is_alive():
        return None

    return output_manager.get_in_queue()


def initialize_parser_worker(log_queue):
    """
    Bootstrap a parser worker process so its log records reach the main process
    output manager and profiling is started.

    This runs inside each worker process, so it rebinds the output manager log
    sink to the shared queue and re-attaches the data-layer logging bridge
    before starting profiling.

    :param log_queue: The queue that worker log records are written to.
    :return: None
    """
    if log_queue is not None:
        output = LogSink(log_queue)
        configure_data_logging(output)

    start_profiling_no_core()


def register_parser_multiprocessing(output_manager):
    """
    Wire the multiprocessing document parser to the controllers-layer
    collaborators that bootstrap its worker processes.

    :return: None
    """
    log_queue_provider = partial(get_parser_log_queue, output_manager)
    configure_multiprocessing(log_queue_provider, initialize_parser_worker)
