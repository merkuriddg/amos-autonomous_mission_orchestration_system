"""AMOS Plugin Registry — runtime registry for loaded plugins.

Provides query, health aggregation, and serialisation for the REST API.

Usage::

    registry = PluginRegistry()
    registry.add(my_plugin)
    active = registry.get_active()
    status = registry.get_all_status()
"""

import threading
import logging

from core.plugin_base import PluginBase, PluginState

log = logging.getLogger("amos.plugins")


class PluginRegistry:
    """Thread-safe runtime registry of loaded plugins."""

    def __init__(self):
        self._plugins: dict[str, PluginBase] = {}    # name → instance
        self._errors: dict[str, dict] = {}           # name → error info
        self._disabled: dict[str, dict] = {}         # name → manifest
        self._lock = threading.Lock()

    # ── Mutators ───────────────────────────────────────────

    def add(self, plugin: PluginBase) -> None:
        """Register a plugin instance."""
        with self._lock:
            self._plugins[plugin.PLUGIN_NAME] = plugin

    def remove(self, name: str) -> PluginBase | None:
        """Remove and return a plugin by name."""
        with self._lock:
            return self._plugins.pop(name, None)

    def record_error(self, name: str, manifest: dict, error: str) -> None:
        """Record a plugin that failed to load."""
        with self._lock:
            self._errors[name] = {
                "name": name,
                "manifest": {k: v for k, v in manifest.items()
                             if not k.startswith("_")},
                "error": error,
                "state": PluginState.ERRORED.value,
            }

    def record_disabled(self, name: str, manifest: dict) -> None:
        """Record a plugin that was disabled in its manifest."""
        with self._lock:
            self._disabled[name] = {
                "name": name,
                "manifest": {k: v for k, v in manifest.items()
                             if not k.startswith("_")},
                "state": PluginState.DISABLED.value,
            }

    # ── Queries ────────────────────────────────────────────

    def get(self, name: str) -> PluginBase | None:
        """Get a plugin by name."""
        with self._lock:
            return self._plugins.get(name)

    def get_all(self) -> list[PluginBase]:
        """Return all registered plugin instances."""
        with self._lock:
            return list(self._plugins.values())

    def get_active(self) -> list[PluginBase]:
        """Return only plugins in ACTIVE state."""
        with self._lock:
            return [p for p in self._plugins.values()
                    if p.state == PluginState.ACTIVE]

    def get_by_type(self, plugin_type: str) -> list[PluginBase]:
        """Query plugins by type (e.g. 'asset_adapter')."""
        with self._lock:
            return [p for p in self._plugins.values()
                    if p.PLUGIN_TYPE == plugin_type]

    def get_by_domain(self, domain: str) -> list[PluginBase]:
        """Query plugins by domain (e.g. 'air', 'ground')."""
        with self._lock:
            return [p for p in self._plugins.values()
                    if p.manifest.get("domain") == domain]

    # ── Health ─────────────────────────────────────────────

    def health_check_all(self) -> list[dict]:
        """Run health check on all registered plugins."""
        with self._lock:
            return [p.health_check() for p in self._plugins.values()]

    # ── Serialisation (for API) ────────────────────────────

    def get_all_status(self) -> list[dict]:
        """Return status of every plugin (active + errored + disabled)."""
        status = []
        with self._lock:
            for p in self._plugins.values():
                status.append(p.to_dict())
            for info in self._errors.values():
                status.append(info)
            for info in self._disabled.values():
                status.append(info)
        return status

    def get_plugin_status(self, name: str) -> dict | None:
        """Return detailed status for a single plugin."""
        with self._lock:
            plugin = self._plugins.get(name)
            if plugin:
                d = plugin.to_dict()
                d["health"] = plugin.health_check()
                return d
            if name in self._errors:
                return self._errors[name]
            if name in self._disabled:
                return self._disabled[name]
        return None

    def get_summary(self) -> dict:
        """Return aggregate counts for the startup banner."""
        with self._lock:
            return {
                "total": len(self._plugins) + len(self._errors) + len(self._disabled),
                "active": sum(1 for p in self._plugins.values()
                              if p.state == PluginState.ACTIVE),
                "errored": len(self._errors),
                "disabled": len(self._disabled),
            }
