"""
应用配置管理 - 适配FastAPI后端
"""
"""
Application constants for FastAPI backend
"""

# 支持的图像格式
SUPPORTED_IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}

# 支持的视频格式
SUPPORTED_VIDEO_FORMATS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv'}

# 数据集类型
DATASET_TYPES = {
    'image': '图像数据集',
    'video': '视频数据集',
    'single_control_image': '单图控制数据集',
    'multi_control_image': '多图控制数据集'
}

# 训练任务类型
TRAINING_TYPES = {
    'qwen_image_lora': 'Qwen-Image LoRA',
    'kontext_lora': 'Kontext LoRA',
    'wan22_lora': 'WAN2.2 LoRA'
}

# 训练状态
TRAINING_STATES = {
    'pending': '待开始',
    'running': '训练中',
    'completed': '已完成',
    'failed': '失败',
    'cancelled': '已取消'
}

# AI模型类型
AI_MODEL_TYPES = {
    'lm_studio': 'LM Studio',
    'gpt': 'OpenAI GPT',
    'local': '本地模型'
}

# 默认提示词
DEFAULT_LABELING_PROMPT = """你是一名图像理解专家，请根据以下图片内容，生成自然流畅、具体清晰的图像描述。要求如下：
1. 使用简洁准确的中文句子，使用逗号进行连接；
2. 避免使用"图中"、"这是一张图片"等冗余措辞；
3. 语言风格自然、具象，不使用抽象形容词或主观感受；
4. 描述的内容不要重复
5. 将描述结构划分为以下模块，并标明模块标题；

【输出格式】
请按以下模块生成描述：
【主体与外貌】
【服饰与道具】
【动作与姿态】
【环境与场景】
【氛围与光效】
【镜头视角信息】

开始生成"""

DEFAULT_TRANSLATION_PROMPT = """【FLUX LoRA 图像打标专用翻译 Prompt】
将下方中文描述翻译为英文，严格遵守以下硬性规则：

1.准确传达原意，不得加入任何主观润色或感情色彩修饰。
2.全句仅使用主动语态，每句动作锚点必须前置，静态锚点必须具备可视化实体描述。
3.每个视觉锚点必须拆解成一句独立短句，禁止在同一句出现多个动作、道具、服饰或背景信息。
4.句子顺序固定为：主体外貌 → 动作姿态 → 服饰道具 → 场景背景 → 光效氛围，严禁顺序颠倒。
5.句子之间仅使用英文逗号, 连接，不允许句子内部使用逗号。
6.禁止使用"and / but / or"等连词，禁止使用被动语态，禁止任何修饰性从句。
7.输出格式为：一整行英文逗号串，最后以英文句号. 结尾。
8.仅输出英文翻译，不要输出任何标签、换行或解释说明。

开始翻译："""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict


class ModelPaths:
    """模型路径配置 - 动态字典包装类，支持属性访问"""

    def __init__(self, data: Optional[Dict[str, Any]] = None):
        self._data = data or {}

    def __getattr__(self, name: str):
        if name.startswith('_'):
            return object.__getattribute__(self, name)

        # 返回嵌套的字典包装对象
        value = self._data.get(name)
        if isinstance(value, dict):
            return self._DictWrapper(value)
        elif value is None:
            # 如果不存在，返回空的字典包装对象，避免训练时取值失败
            empty_dict = {}
            self._data[name] = empty_dict
            return self._DictWrapper(empty_dict)
        return value

    def __setattr__(self, name: str, value):
        if name.startswith('_'):
            object.__setattr__(self, name, value)
        else:
            self._data[name] = value

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self._data

    class _DictWrapper:
        """嵌套字典包装器，支持属性访问"""
        def __init__(self, data: Dict[str, Any]):
            self._data = data

        def __getattr__(self, name: str):
            if name.startswith('_'):
                return object.__getattribute__(self, name)
            return self._data.get(name, "")

        def __setattr__(self, name: str, value):
            if name.startswith('_'):
                object.__setattr__(self, name, value)
            else:
                self._data[name] = value


@dataclass
class LabelingConfig:
    """打标配置 - 使用动态字典存储各 Provider 的配置"""
    default_prompt: str = ""
    translation_prompt: str = ""
    selected_model: str = "lm_studio"
    delay_between_calls: float = 2.0
    models: Dict[str, Dict[str, Any]] = None  # 动态字典：{provider_id: {field_key: value}}

    def __post_init__(self):
        if not self.default_prompt:
            self.default_prompt = "请详细描述这张图片的内容，包括主要物体、颜色、场景、风格等。"
        if not self.translation_prompt:
            self.translation_prompt = "请将以下英文标注翻译成中文："
        if self.models is None:
            self.models = {}


@dataclass
class MusubiConfig:
    """Musubi训练器配置"""
    git_repository: str = "https://github.com/kohya-ss/musubi-tuner.git"
    git_branch: str = "main"
    installation_path: str = "./runtime/engines/musubi-tuner"
    status: str = "unknown"  # installed, updating, error, not_found
    version: str = ""
    last_check: str = ""


@dataclass
class TrainingConfig:
    """训练配置"""
    default_epochs: int = 16
    default_batch_size: int = 2
    default_learning_rate: float = 1e-4
    default_resolution: str = "1024,1024"
    memory_presets: Dict[str, Dict[str, Any]] = None

    def __post_init__(self):
        if self.memory_presets is None:
            self.memory_presets = {
                "low": {"fp8_base": True, "fp8_scaled": True, "blocks_to_swap": 45},
                "medium": {"fp8_base": True, "fp8_scaled": True, "blocks_to_swap": 16},
                "high": {"fp8_base": False, "fp8_scaled": False, "blocks_to_swap": 0}
            }


@dataclass
class StorageConfig:
    """存储配置"""
    workspace_root: str = "./workspace"
    datasets_dir: str = "datasets"
    cache_dir: str = "cache"
    models_dir: str = "models"
    medium_max_side: int = 1280
    preview_max_side: int = 512


@dataclass
class UIConfig:
    """界面配置"""
    theme_mode: str = "light"
    window_width: int = 1400
    window_height: int = 900
    cards_per_row: int = 4


@dataclass
class LoggingConfig:
    """日志与推送配置"""
    # LogSink 批量推送阈值（行数）
    log_batch_lines: int = 25
    # LogSink 最长批量间隔（秒）
    log_batch_interval: float = 0.5


@dataclass
class AppConfig:
    """应用主配置"""
    model_paths: ModelPaths
    labeling: LabelingConfig
    training: TrainingConfig
    musubi: MusubiConfig
    storage: StorageConfig
    ui: UIConfig
    logging: LoggingConfig

    def __init__(self):
        self.model_paths = ModelPaths()
        self.labeling = LabelingConfig()
        self.training = TrainingConfig()
        self.musubi = MusubiConfig()
        self.storage = StorageConfig()
        self.ui = UIConfig()
        self.logging = LoggingConfig()


# 全局配置实例
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """获取全局配置"""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config(config_path: Optional[str] = None) -> AppConfig:
    """重新加载配置文件，刷新内存中的全局配置"""
    global _config
    _config = load_config(config_path)
    return _config


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """加载配置文件"""
    if config_path is None:
        config_path = get_config_path()

    config = AppConfig()

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 更新配置
            if 'model_paths' in data:
                mp_data = data['model_paths']
                # 直接使用 JSON 数据，不做任何 _groups 处理
                config.model_paths = ModelPaths(mp_data)
                    
            if 'labeling' in data:
                labeling_data = data['labeling']

                # 直接使用动态字典加载 models 配置
                models_dict = labeling_data.get('models', {})

                config.labeling = LabelingConfig(
                    default_prompt=labeling_data.get('default_prompt', ''),
                    translation_prompt=labeling_data.get('translation_prompt', ''),
                    selected_model=labeling_data.get('selected_model') or labeling_data.get('model_type', 'lm_studio').lower(),  # 向后兼容
                    delay_between_calls=labeling_data.get('delay_between_calls', 2.0),
                    models=models_dict  # 直接使用字典，不转换为 dataclass
                )
                            
            if 'training' in data:
                config.training = TrainingConfig(**data['training'])
            if 'musubi' in data:
                config.musubi = MusubiConfig(**data['musubi'])
            if 'storage' in data:
                config.storage = StorageConfig(**data['storage'])
            if 'ui' in data:
                config.ui = UIConfig(**data['ui'])
            if 'logging' in data:
                try:
                    config.logging = LoggingConfig(**data['logging'])
                except Exception:
                    # 兼容旧配置或字段缺失
                    pass

        except Exception as e:
            from ..utils.logger import log_warning
            log_warning(f"加载配置失败 {config_path}: {e}")
            # 使用默认配置

    return config


def save_config(config: Optional[AppConfig] = None, config_path: Optional[str] = None):
    """保存配置文件"""
    if config is None:
        config = get_config()

    if config_path is None:
        config_path = get_config_path()

    # 确保配置目录存在
    os.makedirs(os.path.dirname(config_path), exist_ok=True)

    # 转换为字典（已包含 _groups）
    model_paths_dict = config.model_paths.to_dict()

    config_data = {
        'model_paths': model_paths_dict,
        'labeling': {
            'default_prompt': config.labeling.default_prompt,
            'translation_prompt': config.labeling.translation_prompt,
            'selected_model': config.labeling.selected_model,
            'delay_between_calls': config.labeling.delay_between_calls,
            'models': config.labeling.models  # 直接使用字典，无需转换
        },
        'training': asdict(config.training),
        'musubi': asdict(config.musubi),
        'storage': asdict(config.storage),
        'ui': asdict(config.ui),
        'logging': asdict(config.logging)
    }

    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        from ..utils.logger import log_error
        log_error(f"保存配置失败 {config_path}: {e}")


def get_config_path() -> str:
    """获取配置文件路径"""
    return os.path.join(get_app_data_dir(), "config.json")


def get_app_data_dir() -> str:
    """获取应用数据目录"""
    import sys

    # 打包后使用用户数据目录（可写），开发环境使用项目配置目录
    if getattr(sys, 'frozen', False):
        # 打包环境：使用 AppData 目录（Windows）或 ~/.config（Linux/macOS）
        if sys.platform == 'win32':
            app_data = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
            config_dir = app_data / 'EasyTuner'
        else:
            config_dir = Path.home() / '.config' / 'EasyTuner'
    else:
        # 开发环境：使用backend目录存储配置文件
        backend_dir = Path(__file__).parent.parent.parent
        config_dir = backend_dir / "config"

    config_dir.mkdir(parents=True, exist_ok=True)
    return str(config_dir)


def update_config(**kwargs):
    """更新配置"""
    config = get_config()

    for key, value in kwargs.items():
        if hasattr(config, key):
            if isinstance(getattr(config, key), dict):
                getattr(config, key).update(value)
            else:
                setattr(config, key, value)

    save_config(config)
