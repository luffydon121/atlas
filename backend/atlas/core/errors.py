class SourceUnavailable(Exception):
    """A provider could not be reached and no cached copy exists."""

    def __init__(self, source: str, reason: str):
        super().__init__(f"{source}: {reason}")
        self.source = source
        self.reason = reason


class NotCovered(SourceUnavailable):
    """The provider works, but this item is outside what it covers."""


class SourceNotConfigured(SourceUnavailable):
    """A provider needs an optional free key or contact that has not been set."""
