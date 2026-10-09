# Translation hack. Needed for tests completion.
import builtins

if not hasattr(builtins, "_"):
    builtins._ = lambda text: text
