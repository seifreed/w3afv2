"""Configure the headers sent by the HTTP opener."""

from collections.abc import Callable

from w3af.core.exceptions import BaseFrameworkException


class HeaderSettings:
    """Manage default, configured, and file-based request headers."""

    def __init__(self, configuration, log_debug: Callable[..., None]) -> None:
        self._configuration = configuration
        self._log_debug = log_debug
        self.header_list = [("User-Agent", "w3af.org")]

    def set_headers_file(self, headers_file) -> None:
        if not headers_file:
            return

        try:
            with open(headers_file) as file_handle:
                lines = file_handle.readlines()
        except OSError as error:
            msg = 'Unable to open headers file: "%s"'
            raise BaseFrameworkException(msg % headers_file) from error

        header_list = []
        for line in lines:
            header_name = line.split(":")[0]
            header_value = ":".join(line.split(":")[1:]).strip()
            header_list.append((header_name, header_value))

        self.set_header_list(header_list)
        self._configuration.save("headers_file", headers_file)

    def set_header_list(self, header_list) -> None:
        for header_name, header_value in header_list:
            self.header_list.append((header_name, header_value))
            self._log_debug(
                'Added the following header: "%s: %s"',
                header_name,
                header_value,
            )

    def set_user_agent(self, user_agent) -> None:
        self.header_list = [
            header
            for header in self.header_list
            if header[0].lower() != "User-Agent".lower()
        ]
        self.header_list.append(("User-Agent", user_agent))
        self._configuration.save("user_agent", user_agent)
