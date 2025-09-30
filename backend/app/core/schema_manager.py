"""
模型路径Schema管理器
启动时从模型注册表初始化，运行时提供缓存访问
"""

from typing import Dict, Set, Any, List
from dataclasses import fields


class ModelPathsSchemaManager:
    """模型路径Schema管理器 - 单例模式"""

    _instance = None
    _schema_cache: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def initialize(self):
        """启动时从模型注册表初始化schema"""
        from .training.models import list_models

        self._schema_cache.clear()

        for spec in list_models():
            if not spec.path_mapping:
                continue

            # 从dataclass提取字段信息
            model_fields = []
            for field_key, setting_path in spec.path_mapping.items():
                field_info = self._get_field_info(spec.config_cls, field_key)
                model_fields.append({
                    "key": field_key,
                    "label": field_info.get("label", field_key),
                    "help": field_info.get("help", ""),
                    "setting_path": setting_path
                })

            self._schema_cache[spec.type_name] = {
                "title": spec.title,
                "fields": model_fields
            }

        print(f"ModelPathsSchemaManager初始化完成，加载了 {len(self._schema_cache)} 个模型配置")

    def get_schema(self) -> Dict[str, Any]:
        """获取当前schema（从缓存）"""
        return self._schema_cache.copy()

    def get_valid_paths(self) -> Set[str]:
        """获取所有有效的配置路径"""
        paths = set()
        for model_data in self._schema_cache.values():
            for field in model_data["fields"]:
                paths.add(field["setting_path"])
        return paths

    def clean_config(self, config: Dict) -> Dict:
        """按当前schema清理配置，移除无效字段"""
        valid_paths = self.get_valid_paths()
        cleaned = {}

        # 只保留有效路径的值
        for path in valid_paths:
            value = self._get_nested_value(config, path)
            if value:  # 非空才保存
                self._set_nested_value(cleaned, path, value)

        # 保留非model_paths的其他配置
        for key in config:
            if key != "model_paths":
                cleaned[key] = config[key]

        return cleaned

    def _get_field_info(self, config_cls, field_name: str) -> Dict[str, Any]:
        """从dataclass获取字段元数据"""
        try:
            for f in fields(config_cls):
                if f.name == field_name:
                    return f.metadata or {}
        except Exception:
            pass
        return {}

    def _get_nested_value(self, data: Dict, path: str) -> str:
        """获取嵌套值: model_paths.qwen_image.dit_path"""
        keys = path.split('.')
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, {})
            else:
                return ""
        return value if not isinstance(value, dict) else ""

    def _set_nested_value(self, data: Dict, path: str, value: str):
        """设置嵌套值"""
        keys = path.split('.')
        current = data
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value


# 全局实例
schema_manager = ModelPathsSchemaManager()