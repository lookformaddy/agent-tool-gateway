"""Hash-chained audit log.

Each entry's hash covers the previous entry's hash plus the entry's
canonical JSON payload, so deleting or editing any past entry breaks
verification of every entry after it. Verification is O(n) and pure.
"""

from __future__ import annotations

import hashlib
import json

from .models import AuditEntry

GENESIS_HASH = "0" * 64


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def hash_arguments(arguments: dict) -> str:
    return hashlib.sha256(_canonical(arguments).encode()).hexdigest()


class AuditLog:
    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def append(
        self,
        *,
        timestamp: str,
        agent_id: str,
        tenant_id: str,
        tool_name: str,
        version: str,
        decision: str,
        reason: str,
        latency_ms: float,
        cost_usd: float,
        idempotency_key: str | None = None,
        arguments_hash: str = "",
    ) -> AuditEntry:
        prev = self._entries[-1].entry_hash if self._entries else GENESIS_HASH
        payload = {
            "seq": len(self._entries) + 1,
            "timestamp": timestamp,
            "prev_hash": prev,
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "tool_name": tool_name,
            "version": version,
            "decision": decision,
            "reason": reason,
            "latency_ms": latency_ms,
            "cost_usd": cost_usd,
            "idempotency_key": idempotency_key,
            "arguments_hash": arguments_hash,
        }
        entry_hash = hashlib.sha256(
            (prev + _canonical(payload)).encode()
        ).hexdigest()
        entry = AuditEntry(entry_hash=entry_hash, **payload)
        self._entries.append(entry)
        return entry

    def entries(self) -> list[AuditEntry]:
        return list(self._entries)

    def verify(self) -> bool:
        prev = GENESIS_HASH
        for entry in self._entries:
            payload = {
                "seq": entry.seq,
                "timestamp": entry.timestamp,
                "prev_hash": entry.prev_hash,
                "agent_id": entry.agent_id,
                "tenant_id": entry.tenant_id,
                "tool_name": entry.tool_name,
                "version": entry.version,
                "decision": entry.decision,
                "reason": entry.reason,
                "latency_ms": entry.latency_ms,
                "cost_usd": entry.cost_usd,
                "idempotency_key": entry.idempotency_key,
                "arguments_hash": entry.arguments_hash,
            }
            if entry.prev_hash != prev:
                return False
            if entry.entry_hash != hashlib.sha256(
                (prev + _canonical(payload)).encode()
            ).hexdigest():
                return False
            prev = entry.entry_hash
        return True
