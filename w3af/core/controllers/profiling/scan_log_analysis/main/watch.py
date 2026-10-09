import sys
import time

from utils.utils import clear_screen

from . import main as analysis_functions


def watch(scan_log_filename, scan, function_name):
    scan.seek(0)

    while True:
        try:
            # Hack me here
            output = getattr(analysis_functions, function_name)(scan_log_filename, scan)
        except KeyboardInterrupt:
            sys.exit(0)
        except Exception as e:
            print(f"Exception: {e}")
            sys.exit(1)
        else:
            if output is not None:
                output.to_console()

            time.sleep(5)
            clear_screen()
