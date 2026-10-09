import base64
import subprocess
import sys

sys.stdout.write("15825b40c6dace2a"[::-1])
if "__CMD_TO_RUN__":
    sys.stdout.write(
        base64.b64encode(subprocess.getoutput("__CMD_TO_RUN__").encode("utf-8")).decode(
            "ascii"
        )
    )
sys.stdout.write("7cf5d4ab8ed434d5"[::-1])
sys.stdout.flush()
