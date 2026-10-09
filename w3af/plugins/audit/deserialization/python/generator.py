import base64
import time

from w3af.core.data.misc import serialize


class DelayUsingSleep1:
    def __reduce__(self):
        return time.sleep, (1,)


class DelayUsingSleep22:
    def __reduce__(self):
        return time.sleep, (22,)


dump = serialize.dumps(DelayUsingSleep1())
payload = base64.b64encode(dump)

print(f'Save this to pickle.json "1": {payload}')

dump = serialize.dumps(DelayUsingSleep22())
payload = base64.b64encode(dump)

print(f'Save this to pickle.json "2": {payload}')

print("Manually check the offsets of the 1 and 22 strings and save them to pickle.json")
