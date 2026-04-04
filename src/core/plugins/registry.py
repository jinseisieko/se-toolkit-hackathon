"""Plugin registry — Factory pattern for dynamic plugin instantiation.

Provides centralized registration, discovery, and creation of log parser
plugins.  Plugin instantiation errors are wrapped with context so that
one broken plugin never silently breaks the registry.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from src.core.plugins.parser_plugin import (
    LogParserPlugin,
    PluginAlreadyRegisteredError,
    PluginInstantiationError,
)

logger = logging.getLogger(__name__)


class PluginNotFoundError(Exception):
    """Raised when ``create()`` is called with an unregistered name."""


class ParserRegistry:
    """Dynamic plugin discovery and instantiation.

    Plugins are registered by class.  The ``create()`` factory method
    instantiates a plugin by name with an injected config dict.
    """

    def __init__(self, plugin_dirs: Optional[List[Path]] = None) -> None:
        """Initialise an empty registry.

        Args:
            plugin_dirs: Directories to scan for plugin modules.
                Currently unused — plugins are registered explicitly.
                Reserved for future auto-discovery via ``importlib``.
        """
        self._plugins: Dict[str, Type[LogParserPlugin]] = {}
        self._plugin_dirs = plugin_dirs or []

    def register(
        self, name: str, parser_cls: Type[LogParserPlugin]
    ) -> None:
        """Register a plugin class under an explicit name.

        Args:
            name: Unique identifier for this plugin.  Must match the
                value returned by ``plugin_cls(config).name``.
            parser_cls: A concrete subclass of ``LogParserPlugin``.

        Raises:
            PluginAlreadyRegisteredError: If *name* is already registered.
        """
        if name in self._plugins:
            raise PluginAlreadyRegisteredError(
                f"Plugin '{name}' is already registered"
            )
        self._plugins[name] = parser_cls
        logger.debug("Registered parser plugin: %s", name)

    def create(
        self, name: str, config: Optional[Dict[str, Any]] = None
    ) -> LogParserPlugin:
        """Instantiate a registered plugin with the given config.

        Args:
            name: The unique plugin name (matches ``plugin.name``).
            config: Arbitrary key-value configuration forwarded to the
                plugin's ``__init__``.

        Returns:
            An initialised plugin instance.

        Raises:
            PluginNotFoundError: If *name* is not registered.
            PluginInstantiationError: If the plugin's ``__init__`` raises.
        """
        plugin_cls = self._plugins.get(name)
        if plugin_cls is None:
            available = ", ".join(sorted(self._plugins))
            raise PluginNotFoundError(
                f"Plugin '{name}' not found. Available: {available}"
            )

        try:
            return plugin_cls(config=config)
        except Exception as exc:
            raise PluginInstantiationError(
                f"Failed to instantiate plugin '{name}': {exc}"
            ) from exc

    def list_available(self) -> List[str]:
        """Return a sorted list of registered plugin names.

        Returns:
            Alphabetically sorted plugin name strings.
        """
        return sorted(self._plugins)
