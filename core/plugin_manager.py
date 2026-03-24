import importlib
import os
from typing import Optional

from plugins.base import GamePlugin
from core.config_manager import ConfigManager


# Mapping from plugin_id to (module_path, tool_config_key)
PLUGIN_REGISTRY = {
    "maa_arknights": ("plugins.maa_arknights.adapter", "maa"),
    "maaend_endfield": ("plugins.maaend_endfield.adapter", "maaend"),
    "okww_wutheringwaves": ("plugins.okww_wutheringwaves.adapter", "okww"),
}


class PluginManager:
    """Discovers, loads, and manages game plugins."""

    def __init__(self, config_manager: ConfigManager):
        self._config = config_manager
        self._plugins: dict[str, GamePlugin] = {}

    def load_all(self) -> None:
        for plugin_id, (module_path, config_key) in PLUGIN_REGISTRY.items():
            try:
                module = importlib.import_module(module_path)
                # Each adapter module must have a get_plugin() function
                plugin: GamePlugin = module.get_plugin()
                tool_config = self._config.get_tool_config(config_key)
                plugin.load_config(tool_config)
                self._plugins[plugin_id] = plugin
            except Exception as e:
                print(f"Failed to load plugin {plugin_id}: {e}")

    def get_plugin(self, plugin_id: str) -> Optional[GamePlugin]:
        return self._plugins.get(plugin_id)

    def get_all_plugins(self) -> dict[str, GamePlugin]:
        return self._plugins

    def update_plugin_config(self, plugin_id: str, config: dict) -> None:
        """Update a plugin's tool config and reload it."""
        info = PLUGIN_REGISTRY.get(plugin_id)
        if not info:
            return
        _, config_key = info
        self._config.set_tool_config(config_key, config)
        self._config.save()
        plugin = self._plugins.get(plugin_id)
        if plugin:
            plugin.load_config(config)
