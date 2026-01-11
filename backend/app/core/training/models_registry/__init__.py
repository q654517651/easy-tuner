"""
模型定义自动注册模块
显式导入所有模型定义文件，触发模型注册

⚠️ 注意：导入此模块会自动执行注册逻辑，请确保在合适的时机导入
"""

# 显式导入所有模型定义文件（支持打包后运行）
# 动态扫描在打包后会失败，因此改为显式导入
try:
    from . import qwen      # Qwen 系列模型
except ImportError as e:
    from ....utils.logger import log_warning
    log_warning(f"Qwen 模型导入失败: {e}")

try:
    from . import wan       # Wan 系列模型
except ImportError as e:
    from ....utils.logger import log_warning
    log_warning(f"Wan 模型导入失败: {e}")

try:
    from . import flux      # Flux 系列模型
except ImportError as e:
    from ....utils.logger import log_warning
    log_warning(f"Flux 模型导入失败: {e}")

try:
    from . import zimage    # Z-Image 模型
except ImportError as e:
    from ....utils.logger import log_warning
    log_warning(f"Z-Image 模型导入失败: {e}")

# 导出说明：此模块不需要显式导出任何内容
# 导入此模块的副作用是自动注册所有模型到全局注册表
#
# 添加新模型方法：
# 1. 在 models_registry/ 目录下创建新的 .py 文件
# 2. 在上面添加对应的显式导入语句
