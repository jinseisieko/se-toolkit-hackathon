"""Unit tests for ParserRegistry.

Covers:
- Register and create a mock plugin
- Plugin isolation: exception in one plugin doesn't crash registry
- Config injection: plugin receives config dict at instantiation
- List available plugins returns sorted names
- Invalid plugin name raises PluginNotFoundError
- Duplicate registration raises PluginAlreadyRegisteredError
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
import threading

import pytest

from src.core.plugins.parser_plugin import (
    DetectionRule,
    LogParserPlugin,
    ParsedEntry,
    PluginAlreadyRegisteredError,
    PluginInstantiationError,
    Severity,
)
from src.core.plugins.registry import ParserRegistry, PluginNotFoundError

from tests.unit.plugins.conftest import FailingPlugin, MockPlugin


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def registry() -> ParserRegistry:
    return ParserRegistry()


@pytest.fixture
def registered_registry(registry: ParserRegistry) -> ParserRegistry:
    registry.register("mock_plugin", MockPlugin)
    return registry


# ── Happy path ────────────────────────────────────────────────


class TestParserRegistryHappyPath:
    def test_register_and_create_plugin(
        self, registry: ParserRegistry
    ) -> None:
        registry.register("mock_plugin", MockPlugin)
        plugin = registry.create("mock_plugin", {})

        assert isinstance(plugin, MockPlugin)
        assert plugin.name == "mock_plugin"
        assert plugin.default_log_path == "/var/log/mock.log"

    def test_create_passes_config_to_plugin(
        self, registry: ParserRegistry
    ) -> None:
        """Verify the config dict is forwarded to plugin __init__."""

        class ConfigPlugin(LogParserPlugin):
            def __init__(
                self, config: Optional[Dict[str, Any]] = None
            ) -> None:
                self._config = config or {}

            @property
            def name(self) -> str:
                return "config_plugin"

            @property
            def default_log_path(self) -> str:
                return self._config.get("log_path", "/var/log/default.log")

            def parse_line(self, line: str) -> Optional[ParsedEntry]:
                return None

            def get_indicators(self) -> List[DetectionRule]:
                return []

            def process_stream(
                self,
                file_path: str,
                callback: Callable[[ParsedEntry], None],
                stop_event: Optional[threading.Event] = None,
            ) -> None:
                return None

        registry.register("config_plugin", ConfigPlugin)
        plugin = registry.create(
            "config_plugin", {"log_path": "/var/log/custom.log"}
        )

        assert plugin.default_log_path == "/var/log/custom.log"

    def test_list_available_returns_sorted_names(
        self, registry: ParserRegistry
    ) -> None:
        class BetaPlugin(MockPlugin):
            @property
            def name(self) -> str:
                return "beta_plugin"

        class AlphaPlugin(MockPlugin):
            @property
            def name(self) -> str:
                return "alpha_plugin"

        registry.register("beta_plugin", BetaPlugin)
        registry.register("alpha_plugin", AlphaPlugin)

        names = registry.list_available()
        assert names == ["alpha_plugin", "beta_plugin"]

    def test_list_available_empty_registry(
        self, registry: ParserRegistry
    ) -> None:
        assert registry.list_available() == []

    def test_parse_line_delegates_to_plugin(
        self, registered_registry: ParserRegistry
    ) -> None:
        plugin = registered_registry.create("mock_plugin", {})
        result = plugin.parse_line("MOCK event from 10.0.0.1")

        assert result is not None
        assert result.service == "mock"
        assert str(result.ip) == "10.0.0.1"

    def test_parse_line_returns_none_for_non_matching(
        self, registered_registry: ParserRegistry
    ) -> None:
        plugin = registered_registry.create("mock_plugin", {})
        result = plugin.parse_line("normal log line with nothing special")

        assert result is None

    def test_get_indicators_returns_rules(
        self, registered_registry: ParserRegistry
    ) -> None:
        plugin = registered_registry.create("mock_plugin", {})
        rules = plugin.get_indicators()

        assert len(rules) == 1
        assert rules[0].name == "mock_detect"
        assert rules[0].severity == Severity.LOW


# ── Edge cases ────────────────────────────────────────────────


class TestParserRegistryEdgeCases:
    def test_create_unknown_plugin_raises(
        self, registry: ParserRegistry
    ) -> None:
        with pytest.raises(PluginNotFoundError) as exc_info:
            registry.create("nonexistent_plugin", {})

        assert "nonexistent_plugin" in str(exc_info.value)

    def test_duplicate_registration_raises(
        self, registry: ParserRegistry
    ) -> None:
        registry.register("mock_plugin", MockPlugin)
        with pytest.raises(PluginAlreadyRegisteredError):
            registry.register("mock_plugin", MockPlugin)

    def test_plugin_instantiation_failure_raises(
        self, registry: ParserRegistry
    ) -> None:
        registry.register("failing_plugin", FailingPlugin)

        with pytest.raises(PluginInstantiationError) as exc_info:
            registry.create("failing_plugin", {})

        assert "Plugin init failed" in str(exc_info.value)
        assert "failing_plugin" in str(exc_info.value)

    def test_plugin_isolation_failing_plugin_does_not_affect_others(
        self, registry: ParserRegistry
    ) -> None:
        """A plugin that fails to init must not break the registry
        or prevent other plugins from working."""
        registry.register("mock_plugin", MockPlugin)
        registry.register("failing_plugin", FailingPlugin)

        # MockPlugin must still be creatable
        plugin = registry.create("mock_plugin", {})
        assert plugin.name == "mock_plugin"

        # FailingPlugin raises when created
        with pytest.raises(PluginInstantiationError):
            registry.create("failing_plugin", {})

        # Both still listed
        assert "mock_plugin" in registry.list_available()
        assert "failing_plugin" in registry.list_available()
