from w3af.core.controllers.console_tables import table
from w3af.plugins.attack.payloads.base_payload import Payload
from w3af.plugins.attack.payloads.payload_utils import (
    get_process_username,
    int_to_dotted_quad,
    parse_proc_net,
    split_proc_net_address,
)


class tcp(Payload):
    """
    This payload shows TCP socket information
    """

    def api_read(self):
        result = {}

        etc = self.shell.read("/etc/passwd")
        # TODO: Read UDP and TCP6?
        parsed_info = parse_proc_net(self.shell.read("/proc/net/tcp"))

        for parsed_line in parsed_info:
            try:
                if parsed_line[1] != "local_address":
                    ip = split_proc_net_address(parsed_line[1])
                    parsed_line[1] = (
                        int_to_dotted_quad(int(ip[0], 16)) + ":" + str(int(ip[1], 16))
                    )

                if parsed_line[2] != "rem_address":
                    ip = split_proc_net_address(parsed_line[2])
                    parsed_line[2] = (
                        int_to_dotted_quad(int(ip[0], 16)) + ":" + str(int(ip[1], 16))
                    )

                if parsed_line[7] == "tm->when":
                    parsed_line[7] = "uid"

                if parsed_line[7] != "uid":
                    parsed_line[7] = get_process_username(etc, parsed_line[7])

                if parsed_line[0] != "sl":
                    key = str(parsed_line[0].replace(":", ""))
                    result[key] = {
                        "local_address": parsed_line[1],
                        "rem_address": parsed_line[2],
                        "st": parsed_line[3],
                        "uid": parsed_line[7],
                        "inode": parsed_line[11],
                    }
            except IndexError:
                pass

        return result

    def run_read(self):
        api_result = self.api_read()

        if not api_result:
            return "No TCP information was identified."
        else:
            rows = []
            rows.append(
                ["Id", "Local Address", "Remote Address", "Status", "User", "Inode"]
            )
            rows.append([])

            for key in api_result:
                local_address = api_result[key]["local_address"]
                rem_address = api_result[key]["rem_address"]
                st = api_result[key]["st"]
                uid = api_result[key]["uid"]
                inode = api_result[key]["inode"]

                rows.append([key, local_address, rem_address, st, uid, inode])

            result_table = table(rows, self.shell._output)
            result_table.draw(80)
            return rows
