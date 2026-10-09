class BaseFrameworkException(Exception):
    """Base exception shared across application layers."""

    def __init__(self, message):
        self.value = str(message)
        super().__init__(self.value)

    def __str__(self):
        return self.value
