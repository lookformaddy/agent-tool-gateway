"""agent-tool-gateway: a secure tool gateway for AI agents."""

from .accounting import CostLedger
from .audit import AuditLog
from .authz import Authorizer
from .errors import (
    ApprovalNotFound,
    ApprovalRequired,
    GatewayError,
    IdempotencyConflict,
    RateLimited,
    ToolExecutionError,
    ToolNotFound,
    ToolTimeout,
    Unauthorized,
    ValidationError,
)
from .gateway import ToolGateway, build_default_gateway
from .models import (
    AgentIdentity,
    Approval,
    RiskTier,
    TenantPolicy,
    ToolCallRequest,
    ToolCallResult,
    ToolDefinition,
)
from .rate_limit import RateLimiter, TokenBucket
from .registry import ToolRegistry

__all__ = [
    "AgentIdentity", "Approval", "ApprovalNotFound", "ApprovalRequired",
    "AuditLog", "Authorizer", "CostLedger", "GatewayError",
    "IdempotencyConflict", "RateLimited", "RateLimiter", "RiskTier",
    "TenantPolicy", "TokenBucket", "ToolCallRequest", "ToolCallResult",
    "ToolDefinition", "ToolExecutionError", "ToolGateway", "ToolNotFound",
    "ToolRegistry", "ToolTimeout", "Unauthorized", "ValidationError",
    "build_default_gateway",
]

__version__ = "0.1.0"
