import os
import importlib.util
import inspect
import sys
from typing import Dict, List, Type
from src.core.logger import get_logger
from src.core.component_system.base import BaseComponent, ComponentContext

logger = get_logger("ComponentLoader")

class ComponentLoader:
    """
    负责扫描、加载和管理组件。
    """
    def __init__(self, context: ComponentContext):
        self.context = context
        self.components: Dict[str, BaseComponent] = {}
        # 组件目录：项目根目录/src/components
        self.component_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "components"
        )

    def load_all_components(self):
        """扫描并加载目录下的所有组件"""
        logger.info(f"[COMPONENT] SCAN_START | dir: {self.component_dir}")
        
        if not os.path.exists(self.component_dir):
            os.makedirs(self.component_dir)
            logger.info(f"[COMPONENT] DIR_CREATED | dir: {self.component_dir}")
            return

        for filename in os.listdir(self.component_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                self.load_component(filename)

    def load_component(self, filename: str):
        """加载单个组件文件"""
        filepath = os.path.join(self.component_dir, filename)
        module_name = f"components.{filename[:-3]}"
        
        try:
            # 动态加载模块
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                
                # 查找 BaseComponent 子类
                found = False
                for name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and issubclass(obj, BaseComponent) and obj is not BaseComponent:
                        self._register_component(name, obj)
                        found = True
                
                if not found:
                    logger.warning(f"[COMPONENT] NO_CLASS_FOUND | file: {filename}")
            else:
                 logger.error(f"[COMPONENT] LOAD_FAIL | file: {filename} | reason: invalid_spec")

        except Exception as e:
            logger.error(f"[COMPONENT] LOAD_ERROR | file: {filename} | error: {e}", exc_info=True)

    def _register_component(self, name: str, cls: Type[BaseComponent]):
        """实例化并注册组件"""
        if name in self.components:
            logger.warning(f"[COMPONENT] DUPLICATE | name: {name}")
            return

        try:
            instance = cls(self.context)
            instance.on_enable()
            self.components[name] = instance
            logger.info(f"[COMPONENT] ENABLED | name: {name}")
        except Exception as e:
            logger.error(f"[COMPONENT] INIT_FAIL | name: {name} | error: {e}", exc_info=True)

    def unload_all_components(self):
        """卸载所有组件"""
        for name, component in self.components.items():
            try:
                component.on_disable()
                logger.info(f"[COMPONENT] DISABLED | name: {name}")
            except Exception as e:
                logger.error(f"[COMPONENT] DISABLE_ERROR | name: {name} | error: {e}")
        self.components.clear()
