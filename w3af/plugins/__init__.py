# Translation hack. Needed for tests completion.
import builtins

if not hasattr(builtins, "_"):
    builtins.__dict__["_"] = lambda text: text
