"""Gateway error types. All failures are explicit, typed, and fail closed.

A denied or failed call never silently proceeds: every error maps to a
decision recorded in the audit log by the gateway.
"""


class GatewayError(Exception):
    """Base class for all gateway errors."""


class ToolNotFound(GatewayError):
    """No registered tool matches the requested name/version."""


class Unauthorized(GatewayError):
    """Fail-closed authorization denial (unknown tenant/agent or missing scope)."""


class ApprovalRequired(GatewayError):
    """A high-risk tool needs a human approval before it may run."""

    def __init__(self, message: str, approval_id: str) -> None:
        super().__init__(message)
        self.approlog_id = approval_id
        self.approval_id = approval_id


class ApprovalNotFound(GatewayError):
    """No pending approval matches the given id."""


class RateLimited(GatewayError):
    """Per-tool rate limit for this agent/tenant is exhausted."""


class ValidationError(GatewayError):
    """Tool arguments (or a tool result) do not match the declared JSON schema."""


class IdempotencyConflict(GatewayError):
    """An idempotency key was reused with a different request payload."""


class ToolTimeout(GatewayError):
    """The tool executor did not finish within the tool's timeout."""


class ToolExecutionError(GatewayError):
    """The executor raised, or its output failed output-schema validation."""
