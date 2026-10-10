import re

from w3af.core.controllers.console_tables import table
from w3af.plugins.attack.payloads.base_payload import Payload


class apache_root_directory(Payload):
    """
    This payload finds Apache Root Directories where websites are hosted.
    """

    def api_read(self):
        result = {}
        directory = []

        def parse_etc_passwd(etc_passwd, user):
            root = re.search("(?<=" + user + r":/)(.*?)\:", etc_passwd)
            if root:
                return root.group(1)
            else:
                return ""

        def parse_config_file(config_file):
            root = re.search("(?<=DocumentRoot )(.*)", config_file)
            if root:
                return root.group(1)
            else:
                return ""

        users = self.exec_payload("apache_run_user")["apache_run_user"]
        if users:
            passwd = self.shell.read("/etc/passwd")
            for user in users:
                directory.append("/" + parse_etc_passwd(passwd, user) + "/")

        apache_config_files = self.exec_payload("apache_config_files")
        apache_config_files = apache_config_files["apache_config"]

        if apache_config_files:
            for file in apache_config_files:
                file_content = self.shell.read(file)
                if parse_config_file(file_content) != "":
                    directory.append(parse_config_file(file_content) + "/")

        webroot = self._knowledge_base.raw_read("pathdisclosure", "webroot")
        if webroot:
            directory.append(webroot)

        # perform some normalization and filtering
        directory = [p.replace("//", "/") for p in directory if p != ""]
        directory = list(set(directory))

        result["apache_root_directory"] = directory

        return result

    def run_read(self):
        api_result = self.api_read()

        if not api_result["apache_root_directory"]:
            return "Apache root directory not found."
        else:
            rows = []
            rows.append(["Apache root directories"])
            rows.append([])
            for key_name in api_result:
                for directory in api_result[key_name]:
                    rows.append(
                        [
                            directory,
                        ]
                    )
            result_table = table(rows, self.shell._output)
            result_table.draw(80)
            return rows
