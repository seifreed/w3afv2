"""Configure the URL parameter handler used by the HTTP opener."""

from w3af.core.data.kb.config import cf as cfg
from w3af.core.data.url.handlers.url_parameter import URLParameterHandler


class URLParameterSettings:
    """Manage the optional parameter appended to every URL."""

    def __init__(self) -> None:
        self.handler: URLParameterHandler | None = None

    def set_url_parameter(self, url_param) -> None:
        url_param = url_param.replace("'", "")
        url_param = url_param.replace('"', "")
        url_param = url_param.strip()

        if url_param:
            cfg.save("url_parameter", url_param)
            self.handler = URLParameterHandler(url_param)
