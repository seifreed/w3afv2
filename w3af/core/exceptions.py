class BaseFrameworkException(Exception):
    """Base exception shared across application layers."""

    def __init__(self, message):
        self.value = str(message)
        super().__init__(self.value)

    def __str__(self):
        return self.value


class BodyCutException(BaseFrameworkException):
    """Raised when response-body extraction boundaries exceed the body."""


class FileException(BaseFrameworkException):
    """Raised when framework-managed file operations fail."""


class ScanMustStopException(Exception):
    """Signal that the current scan must stop."""

    def __init__(self, msg, errs=()):
        self.msg = str(msg)
        self.errs = errs

    def __str__(self):
        msg = str(self.msg)
        if self.errs:
            msg += " The following errors were logged:\n"
            for err in self.errs:
                msg += f"  - {err}"
        return msg

    __repr__ = __str__


class ScanMustStopByUserRequest(ScanMustStopException):
    """The user requested the scan to stop."""


class ScanMustStopOnUrlError(ScanMustStopException):
    """Stop a scan after repeated URL request failures."""

    def __init__(self, url_error, req):
        super().__init__(url_error)
        self.req = req

    def __str__(self):
        return f"Extended URL library error '{self.msg}' while requesting '{self.req.get_full_url()}'."

    __repr__ = __str__


class ScanMustStopByKnownReasonExc(ScanMustStopException):
    def __init__(self, msg, errs=(), reason=None):
        super().__init__(msg, errs)
        self.reason = reason

    def __str__(self):
        message = super().__str__()
        if self.reason:
            message += f" - Reason: {self.reason}"
        return message


class ScanMustStopByUnknownReasonExc(ScanMustStopException):
    def __str__(self):
        message = self.msg
        for error_str in self.errs:
            message += "\n" + error_str
        return message
