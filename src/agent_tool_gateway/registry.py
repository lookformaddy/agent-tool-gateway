"""Versioned tool registry. Registration is append-only per (name, version)."""

from __future__ import annotations

from .errors import ToolNotFound
from .models import ToolDefinition


class ToolRegistry:
    def __init__(self) -> None:
        self._by_key: dict[str, ToolDefinition] = {}
        self._versions: dict[str, list[str]] = {}

    def register(self, definition: ToolDefinition) -> None:
        if definition.key in self._by_key:
            raise ValueError(f"tool already registered: {definition.key}")
        self._by_key[definition.key] = definition
        self._versions.setdefault(definition.name, []).append(definition.version)

    def get(self, name: str, version: str = "latest") -> ToolDefinition:
        if version == "latest":
            versions = self._versions.get(name, [])
            if not versions:
                raise ToolNotFound(f"unknown tool: {name}")
            version = versions[-1]
        definition = self._by_key.get(f"{name}@{version}")
        if definition is None:
            raise ToolNotFound(f"unknown tool version: {name}@{version}")
        return definition

    def list_tools(self) -> list[ToolDefinition]:
        return sorted(self._by_key.values(), key=lambda d: (d.name, d.version))

    def versions_of(self, name: str) -> list[str]:
        return list(self._versions.get(name, []))
