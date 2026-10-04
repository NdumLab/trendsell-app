"""Shared behaviour for server-side live-data adapters.

Provider failures are deliberately reduced to safe classifications before they reach a
job or source-health record.  Response bodies and credentials belong in neither place.
"""


class ProviderError(RuntimeError):
    """A safe error classification suitable for UI/job history."""

    def __init__(self, code: str, detail: str, retry_after: str = 'Manual retry'):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.retry_after = retry_after
