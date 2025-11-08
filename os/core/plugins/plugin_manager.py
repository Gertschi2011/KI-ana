"""
Plugin System

Extensible plugin architecture for KI-ana OS.
"""

import importlib
import sys
from typing import Dict, Any, List, Callable
from pathlib import Path
from loguru import logger
import inspect


class Plugin:
    """Base Plugin class"""
    
    name: str = "Unknown Plugin"
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    
    def initialize(self) -> bool:
        """Initialize the plugin"""
        return True
    
    def execute(self, *args, **kwargs) -> Any:
        """Execute plugin functionality"""
        raise NotImplementedError("Plugin must implement execute()")
    
    def shutdown(self):
        """Cleanup on shutdown"""
        pass


class PluginManager:
    """
    Plugin Management System
    
    Loads and manages plugins:
    - Dynamic loading
    - Plugin discovery
    - Lifecycle management
    - Hook system
    """
    
    def __init__(self, plugin_dir: str = "~/.kiana/plugins"):
        self.plugin_dir = Path(plugin_dir).expanduser()
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        
        self.plugins: Dict[str, Plugin] = {}
        self.hooks: Dict[str, List[Callable]] = {}
        
    def discover_plugins(self) -> List[str]:
        """Discover available plugins"""
        logger.info("🔍 Discovering plugins...")
        
        plugins = []
        
        # Find all .py files in plugin directory
        for plugin_file in self.plugin_dir.glob("*.py"):
            if plugin_file.stem.startswith("_"):
                continue
            plugins.append(plugin_file.stem)
        
        logger.info(f"Found {len(plugins)} plugins")
        return plugins
    
    def load_plugin(self, plugin_name: str) -> bool:
        """Load a specific plugin"""
        logger.info(f"📦 Loading plugin: {plugin_name}")
        
        try:
            # Add plugin dir to path if not already there
            plugin_dir_str = str(self.plugin_dir.absolute())
            if plugin_dir_str not in sys.path:
                sys.path.insert(0, plugin_dir_str)
            
            # Reload if already imported
            if plugin_name in sys.modules:
                module = importlib.reload(sys.modules[plugin_name])
            else:
                # Import plugin module
                module = importlib.import_module(plugin_name)
            
            # Find Plugin class
            plugin_class = None
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, Plugin) and obj != Plugin:
                    plugin_class = obj
                    break
            
            if plugin_class is None:
                logger.error(f"No Plugin class found in {plugin_name}")
                return False
            
            # Instantiate plugin
            plugin = plugin_class()
            
            # Initialize
            if plugin.initialize():
                self.plugins[plugin_name] = plugin
                logger.success(f"✅ Plugin loaded: {plugin.name}")
                return True
            else:
                logger.error(f"Plugin initialization failed: {plugin_name}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_name}: {e}")
            return False
    
    def load_all_plugins(self):
        """Load all discovered plugins"""
        plugins = self.discover_plugins()
        
        for plugin_name in plugins:
            self.load_plugin(plugin_name)
    
    def unload_plugin(self, plugin_name: str):
        """Unload a plugin"""
        if plugin_name in self.plugins:
            plugin = self.plugins[plugin_name]
            plugin.shutdown()
            del self.plugins[plugin_name]
            logger.info(f"Unloaded plugin: {plugin_name}")
    
    def execute_plugin(self, plugin_name: str, *args, **kwargs) -> Any:
        """Execute a plugin"""
        if plugin_name not in self.plugins:
            raise ValueError(f"Plugin not loaded: {plugin_name}")
        
        plugin = self.plugins[plugin_name]
        return plugin.execute(*args, **kwargs)
    
    def register_hook(self, hook_name: str, callback: Callable):
        """Register a hook callback"""
        if hook_name not in self.hooks:
            self.hooks[hook_name] = []
        
        self.hooks[hook_name].append(callback)
        logger.info(f"Registered hook: {hook_name}")
    
    def trigger_hook(self, hook_name: str, *args, **kwargs):
        """Trigger all callbacks for a hook"""
        if hook_name not in self.hooks:
            return
        
        for callback in self.hooks[hook_name]:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Hook callback failed: {e}")
    
    def get_plugin_info(self, plugin_name: str) -> Dict[str, Any]:
        """Get plugin information"""
        if plugin_name not in self.plugins:
            return {}
        
        plugin = self.plugins[plugin_name]
        return {
            "name": plugin.name,
            "version": plugin.version,
            "description": plugin.description,
            "author": plugin.author
        }
    
    def list_plugins(self) -> List[Dict[str, Any]]:
        """List all loaded plugins"""
        return [
            self.get_plugin_info(name)
            for name in self.plugins.keys()
        ]


# Singleton
_plugin_manager_instance = None


def get_plugin_manager() -> PluginManager:
    """Get or create plugin manager singleton"""
    global _plugin_manager_instance
    
    if _plugin_manager_instance is None:
        _plugin_manager_instance = PluginManager()
    
    return _plugin_manager_instance
