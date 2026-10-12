import base64
import json

from w3af.core.controllers.misc.external_process import run_process
from w3af.plugins.audit.deserialization_generator_helpers import (
    find_payload_offsets,
)

# java -jar ysoserial-0.0.6-SNAPSHOT-all.jar -h
PAYLOADS = [
    "BeanShell1",
    "C3P0",
    "Clojure",
    "CommonsBeanutils1",
    "CommonsCollections1",
    "CommonsCollections2",
    "CommonsCollections3",
    "CommonsCollections4",
    "CommonsCollections5",
    "CommonsCollections6",
    "FileUpload1",
    "Groovy1",
    "Hibernate1",
    "Hibernate2",
    "JBossInterceptors1",
    "JRMPClient",
    "JRMPListener",
    "JSON1",
    "JavassistWeld1",
    "Jdk7u21",
    "Jython1",
    "MozillaRhino1",
    "Myfaces1",
    "Myfaces2",
    "ROME",
    "Spring1",
    "Spring2",
    "URLDNS",
    "Wicket1",
]

SLEEP_SAMPLES = {1: ["1", "3"], 2: ["22", "77"]}

YSOSERIAL_JAR = "ysoserial-0.0.6-SNAPSHOT-all.jar"


def get_payload_bin(payload, seconds):
    command = ["java", "-jar", YSOSERIAL_JAR, payload, f"sleep {seconds}"]
    result = run_process(command, text=False)
    if result.returncode != 0:
        raise RuntimeError(f"ysoserial failed for {payload}: {result.stderr!r}")
    return result.stdout


def get_payload_bin_for_command_len(payload, command_len):
    sample_1 = SLEEP_SAMPLES[command_len][0]
    sample_2 = SLEEP_SAMPLES[command_len][1]
    payload_bin_1 = get_payload_bin(payload, sample_1)
    payload_bin_2 = get_payload_bin(payload, sample_2)
    offsets = find_payload_offsets(
        payload_bin_1, payload_bin_2, sample_1, sample_2, command_len
    )
    return payload_bin_1, offsets


def main(payloads):
    for payload in payloads:

        try:
            p1, o1 = get_payload_bin_for_command_len(payload, 1)
            p2, o2 = get_payload_bin_for_command_len(payload, 2)
        except (
            OSError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
            IndexError,
        ) as e:
            args = (payload, e)
            msg = 'Failed to create %s.json, exception: "%s"'
            print(msg % args)
            print("\n\n\n")
            continue

        payload_json = {
            "1": {"payload": base64.b64encode(p1), "offsets": o1},
            "2": {"payload": base64.b64encode(p2), "offsets": o2},
        }

        with open(f"{payload}.json", "w") as json_fh:
            json_fh.write(json.dumps(payload_json, indent=4))
        print(f"Successfully created {payload}.json")
        print("\n\n\n")


if __name__ == "__main__":
    main(PAYLOADS)
