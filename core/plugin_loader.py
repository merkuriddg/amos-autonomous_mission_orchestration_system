"""AMOS Plugin Loader — discovery, validation, and lifecycle management.

Scans a plugin directory for sub-directories containing ``plugin.yaml``,
validates the manifest, dynamically imports the plugin module, and
orchestrates the full lifecycle::

    discover  →  validate  →  import  →  load  →  register  →  activate

Plugins that fail any step are marked ERRORED and logged but never
crash the platform.

Usage::

    from core.event_bus import EventBus
    from core.plugin_loader import PluginLoader

    bus = EventBus()
    loader = PluginLoader("plugins", event_bus=bus)
    results = loader.discover_and_load_all()
"""

import os
import sys
import importlib
import inspect
import logging

import yaml

from core.plugin_base import PluginBase, PluginState
from core.plugin_registry import PluginRegistry

log = logging.getLogger("amos.plugins")

REQUIRED_MANIFEST_FIELDS = {"name", "version", "type"}


class PluginLoader:
    """Discover, validate, import, and manage AMOS plugin lifecycle.

    Parameters
    ----------
    plugins_dir : str
        Path to the top-level ``plugins/`` directory.
    event_bus : EventBus
        The platform event bus — passed to plugins on activation.
    """

    def __init__(self, plugins_dir: str, event_bus=None):
        self.plugins_dir = os.path.abspath(plugins_dir)
        self.event_bus = event_bus
        self.registry = PluginRegistry()
        self._capability_registry: dict = {}   # shared with plugins

    # ── Public API ─────────────────────────────────────────

    def discover_and_load_all(self) -> dict:
        """Full pipeline: discover → validate → import → load → register → activate.

        Returns a summary dict keyed by plugin name.
        """
        results = {}
        manifests = self._discover()

        for manifest in manifests:
            name = manifest.get("name", "unknown")
            try:
                # Check enabled flag
                if not manifest.get("enabled", True):
                    log.info(f"Plugin '{name}': disabled in manifest — skipping")
                    self.registry.record_disabled(name, manifest)
                    results[name] = "disabled"
                    continue

                # Validate
                self._validate_manifest(manifest)

                # Import
                plugin = self._import_plugin(manifest)

                # Inject manifest metadata
                plugin.manifest = manifest
                if not plugin.PLUGIN_NAME:
                    plugin.PLUGIN_NAME = manifest["name"]
                if not plugin.PLUGIN_VERSION or plugin.PLUGIN_VERSION == "0.0":
                    plugin.PLUGIN_VERSION = str(manifest.get("version", "0.0"))
                if not plugin.PLUGIN_TYPE:
                    plugin.PLUGIN_TYPE = manifest.get("type", "")

                # Load
                plugin.on_load()
                plugin.state = PluginState.LOADED
                log.info(f"Plugin '{name}' v{plugin.PLUGIN_VERSION}: loaded")

                # Register
                plugin.on_register(self._capability_registry)
                plugin.state = PluginState.REGISTERED
                self.registry.add(plugin)

                # Activate
                plugin.event_bus = self.event_bus
                plugin.on_activate(self.event_bus)
                plugin.state = PluginState.ACTIVE
                log.info(f"Plugin '{name}': active")

                # Publish lifecycle event
                if self.event_bus:
                    self.event_bus.publish("plugin.loaded", {
                        "name": name,
                        "version": plugin.PLUGIN_VERSION,
                        "type": plugin.PLUGIN_TYPE,
                    }, source="plugin_loader")

                results[name] = "active"

            except Exception as exc:
                log.error(f"Plugin '{name}' failed: {exc}")
                # Record the error in registry if plugin was partially created
                self.registry.record_error(name, manifest, str(exc))
                if self.event_bus:
                    self.event_bus.publish("plugin.error", {
                        "name": name, "error": str(exc),
                    }, source="plugin_loader")
                results[name] = f"error: {exc}"

        return results

    def shutdown_all(self) -> None:
        """Shutdown all active plugins in reverse order."""
        for plugin in reversed(self.registry.get_active()):
            try:
                plugin.on_shutdown()
                plugin.state = PluginState.SHUTDOWN
                log.info(f"Plugin '{plugin.PLUGIN_NAME}': shutdown")
            except Exception as exc:
                log.error(f"Plugin '{plugin.PLUGIN_NAME}' shutdown error: {exc}")

    def get_capability_registry(self) -> dict:
        """Return the shared capability registry (populated by plugins)."""
        return dict(self._capability_registry)

    # ── Discovery ──────────────────────────────────────────

    def _discover(self) -> list[dict]:
        """Scan plugins_dir for directories containing plugin.yaml."""
        manifests = []
        if not os.path.isdir(self.plugins_dir):
            log.warning(f"Plugins directory not found: {self.plugins_dir}")
            return manifests

        for entry in sorted(os.listdir(self.plugins_dir)):
            plugin_dir = os.path.join(self.plugins_dir, entry)
            manifest_path = os.path.join(plugin_dir, "plugin.yaml")
            if os.path.isdir(plugin_dir) and os.path.isfile(manifest_path):
                try:
                    with open(manifest_path, "r", encoding="utf-8") as fh:
                        manifest = yaml.safe_load(fh) or {}
                    manifest["_dir"] = plugin_dir
                    manifest["_manifest_path"] = manifest_path
                    manifests.append(manifest)
                except Exception as exc:
                    log.error(f"Failed to read {manifest_path}: {exc}")
        return manifests

    # ── Validation ─────────────────────────────────────────

    @staticmethod
    def _validate_manifest(manifest: dict) -> None:
        """Raise ValueError if manifest is invalid."""
        missing = REQUIRED_MANIFEST_FIELDS - set(manifest.keys())
        if missing:
            raise ValueError(f"Missing required manifest fields: {missing}")

    # ── Import ─────────────────────────────────────────────

    def _import_plugin(self, manifest: dict) -> PluginBase:
        """Dynamically import the plugin module and instantiate the plugin class.

        The loader looks for:
        1. ``entry_point`` in manifest (e.g. ``ExampleDronePlugin``)
        2. Any class in __init__.py that extends PluginBase
        3. Any class whose name ends with "Plugin"
        """
        plugin_dir = manifest["_dir"]
        plugin_name = manifest["name"]
        package_name = f"plugins.{os.path.basename(plugin_dir)}"

        # Ensure plugins/ parent is on sys.path
        root = os.path.dirname(self.plugins_dir)
        if root not in sys.path:
            sys.path.insert(0, root)

        # Import the package
        module = importlib.import_module(package_name)

        # Find the plugin class
        entry_point = manifest.get("entry_point")

        if entry_point:
            # Handle module:class notation (e.g. "__init__:MyPlugin")
            if ":" in entry_point:
                entry_point = entry_point.split(":", 1)[1]
            cls = getattr(module, entry_point, None)
            if cls is None:
                raise ImportError(
                    f"Entry point '{entry_point}' not found in {package_name}")
        else:
            # Auto-detect: prefer PluginBase subclass, then *Plugin class
            cls = self._find_plugin_class(module)
            if cls is None:
                raise ImportError(
                    f"No plugin class found in {package_name}. "
                    f"Add 'entry_point' to plugin.yaml or extend PluginBase.")

        return cls()

    @staticmethod
    def _find_plugin_class(module) -> type | None:
        """Find the best plugin class in a module."""
        # First pass: look for PluginBase subclasses
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if (issubclass(obj, PluginBase) and obj is not PluginBase
                    and obj.__module__ == module.__name__):
                return obj

        # Second pass: look for classes ending in "Plugin"
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if name.endswith("Plugin") and obj.__module__ == module.__name__:
                return obj

        return None
