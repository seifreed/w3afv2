import builtins

if "_" not in builtins.__dict__:
    builtins.__dict__["_"] = lambda x: x


def setUpPackage():
    builtins.__dict__["_"] = lambda x: x
