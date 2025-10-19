# TagTragger 项目文档

**语言要求：请使用中文回答所有问题和提供所有技术支持。**

## 项目概述

TagTragger 是一个用于图像/视频数据集管理和 AI 模型训练的工具，主要用于 LoRA 模型训练。

**技术栈：**
- 后端：FastAPI + Python
- 前端：React + TypeScript + Vite + HeroUI
- 训练引擎：musubi-tuner（Git Clone 到 workspace/runtime/engines）

**主要功能：**
1. 数据集管理（图像/视频/控制图）
2. AI 自动打标（支持多种模型）
3. LoRA 模型训练（Qwen-Image、Flux Kontext、Wan2.1/2.2）
4. 训练监控与日志

---

## 核心架构

### 1. 数据集管理架构

**核心文件：**
- `backend/app/core/dataset/manager.py` - 数据集管理器
- `backend/app/core/dataset/models.py` - 数据集模型定义
- `backend/app/services/dataset_service.py` - 数据集服务层
- `backend/app/api/v1/datasets.py` - 数据集 API

**数据集类型：**
```python
class DatasetType(str, Enum):
    IMAGE = "image"                          # 图像数据集
    VIDEO = "video"                          # 视频数据集
    SINGLE_CONTROL_IMAGE = "single_control_image"  # 单图控制
    MULTI_CONTROL_IMAGE = "multi_control_image"    # 多图控制
```

**数据集存储结构：**
```
workspace/
└── datasets/
    └── {dataset_id}/
        ├── metadata.json          # 数据集元数据
        ├── images/                # 原图
        │   ├── {image_id}.{ext}
        │   └── ...
        ├── medium/                # 中等尺寸缩略图 (max_side=1280)
        ├── preview/               # 预览缩略图 (max_side=512)
        ├── captions/              # 标注文本
        │   ├── {image_id}.txt
        │   └── ...
        └── control/               # 控制图（仅控制数据集）
            ├── {image_id}_control.{ext}
            └── ...
```

**关键流程：**
1. 创建数据集 → 生成唯一 ID → 创建目录结构
2. 添加图片 → 保存原图 → 异步生成缩略图 → 更新元数据
3. 删除图片 → 删除文件 → 更新元数据 → 清理空目录

---

### 2. 打标系统架构

**核心文件：**
- `backend/app/core/labeling/ai_client.py` - AI 客户端（动态 Provider 加载）
- `backend/app/core/labeling/providers/` - Provider 实现目录
  - `base_provider.py` - Provider 基类
  - `lm_studio.py` - LM Studio Provider
  - `openai_compatible.py` - OpenAI 兼容 Provider
  - `local_qwen_vl.py` - 本地 Qwen-VL Provider
- `backend/app/services/labeling_service.py` - 打标服务层
- `backend/app/api/v1/datasets.py` - 打标 API（`/api/v1/datasets/{id}/label`）

**Provider 注册机制：**
```python
# providers/__init__.py 中自动扫描并注册
PROVIDER_REGISTRY = {
    "lm_studio": LMStudioProvider,
    "gpt": OpenAICompatibleProvider,
    "local_qwen_vl": LocalQwenVLProvider,
}

# 动态加载：根据配置选择对应的 Provider
provider = PROVIDER_REGISTRY[provider_type](config)
```

**打标流程：**
1. 用户选择数据集图片 → 点击"生成标注"
2. 后端读取图片 → 转 base64 → 调用 AI Provider
3. AI 返回标注 → 保存到 `captions/{image_id}.txt`
4. 支持批量打标（带延迟控制，防止 API 限流）

**配置结构：**
```python
@dataclass
class LabelingConfig:
    default_prompt: str              # 默认提示词
    translation_prompt: str          # 翻译提示词
    selected_model: str              # 当前选择的模型（如 "lm_studio"）
    delay_between_calls: float       # API 调用间隔（秒）
    models: LabelingModelConfigs     # 各模型配置
        - gpt: APIModelConfig
        - lm_studio: APIModelConfig
        - local_qwen_vl: APIModelConfig
```

---

### 3. 训练系统架构

**核心文件：**
- `backend/app/core/training/models.py` - 训练模型注册表（所有模型定义）
- `backend/app/core/training/manager.py` - 训练管理器
- `backend/app/services/training_service.py` - 训练服务层
- `backend/app/api/v1/training.py` - 训练 API

**模型注册表系统：**

所有训练模型都在 `models.py` 中通过 `register_model()` 注册：

```python
register_model(ModelSpec(
    type_name="qwen_image",           # 模型类型名（唯一标识）
    title="Qwen-Image LoRA",          # 显示名称
    config_cls=QwenImage,             # 配置类（dataclass）
    script_train="qwen_image_train_network.py",  # 训练脚本
    network_module="musubi_tuner.networks.lora_qwen_image",
    group_order=[...],                # UI 参数分组顺序
    path_mapping={                    # 模型路径映射
        "dit_path": "model_paths.qwen_image.dit_path",
        "vae_path": "model_paths.qwen_image.vae_path",
        "text_encoder_path": "model_paths.qwen_image.text_encoder_path"
    },
    cache_steps=[...],                # 缓存步骤定义
    features={},                      # 特性开关
    supported_dataset_types=[...]     # 支持的数据集类型
))
```

**已注册的训练模型：**
- `qwen_image` - Qwen-Image LoRA
- `qwen_image_edit` - Qwen-Image Edit LoRA
- `flux_kontext` - Flux Kontext LoRA
- `Wan_2_1` - Wan 2.1 LoRA
- `Wan_2_2` - Wan 2.2 LoRA

**配置类 (dataclass) 结构：**

每个模型的配置类继承自 `BaseTrainingConfig`，通过 `field()` 定义参数：

```python
@dataclass
class QwenImage(BaseTrainingConfig):
    dit_path: str = field(
        default="",
        metadata={
            "group": ParameterGroup.PATH.key,  # 参数分组
            "label": "DiT 模型路径",            # UI 标签
            "widget": "file_picker",           # UI 组件类型
            "help": "提示信息",
            "cli": {                           # CLI 参数映射
                "name": "--dit",
                "type": "value",
                "formatter": "path"
            },
            "ui_hidden": False,                # 是否在 UI 隐藏
            "persist": True                    # 是否持久化保存
        }
    )
    # ... 其他参数
```

**path_mapping 说明：**

`path_mapping` 定义了配置类字段如何从全局配置文件读取：

```python
path_mapping={
    "dit_path": "model_paths.qwen_image.dit_path",
    # ↑ 左边：配置类字段名（必须和 config_cls 中的字段名一致）
    # ↑ 右边：config.json 中的存储路径
}
```

**训练流程：**

1. **创建训练任务**
   - 用户在前端填写训练参数 → 提交到 `/api/v1/training/tasks`
   - 后端根据 `model_type` 查找对应的 `ModelSpec`
   - 从 `path_mapping` 读取模型路径并填充到配置类
   - 创建训练任务记录（状态：pending）

2. **启动训练**
   - TrainingManager 读取任务配置
   - 生成 `dataset.toml` 配置文件
   - 执行 cache_steps（缓存 VAE latents 和 Text Encoder outputs）
   - 构建训练命令行参数（从配置类的 CLI metadata 生成）
   - 启动 musubi-tuner 训练脚本
   - 更新任务状态为 running

3. **训练监控**
   - 实时读取训练日志
   - 解析 TensorBoard 事件文件（loss、learning_rate 等指标）
   - 通过 WebSocket 推送日志和指标到前端

4. **训练完成**
   - 训练进程退出
   - 保存 LoRA 权重到 `workspace/models/{task_id}/`
   - 更新任务状态为 completed

**参数分组系统：**

```python
class ParameterGroup(Enum):
    PATH = ("path", "模型路径", "模型路径信息")
    DATASET = ("dataset", "数据集参数", "数据集相关配置参数")
    BASIC = ("basic", "基础参数", "基础参数")
    OPTIMIZER = ("optimizer", "优化器与调度", "优化器和学习率调度")
    PRECISION = ("precision", "精度与硬件", "混合精度和硬件配置")
    SAMPLING = ("sampling", "采样配置", "训练过程中的图像采样")
    SAVING = ("saving", "保存配置", "模型检查点保存设置")
    ADVANCED = ("advanced", "高级选项", "高级和实验性参数")
```

前端会按照 `group_order` 指定的顺序展示参数组。

---

### 4. 配置管理架构

**核心文件：**
- `backend/app/core/config.py` - 全局配置管理
- `backend/app/core/schema_manager.py` - 模型路径 Schema 管理器
- `backend/config/config.json` - 配置文件

**配置结构：**

```python
@dataclass
class AppConfig:
    model_paths: ModelPaths          # 模型路径（动态字典）
    labeling: LabelingConfig         # 打标配置
    training: TrainingConfig         # 训练配置
    musubi: MusubiConfig            # Musubi 引擎配置
    storage: StorageConfig          # 存储配置
    ui: UIConfig                    # UI 配置
    logging: LoggingConfig          # 日志配置
```

**ModelPaths 动态字典：**

`ModelPaths` 是一个动态字典包装类，支持通过属性访问：

```python
# 访问方式
config.model_paths.qwen_image.dit_path
config.model_paths.flux_kontext.text_encoder1_path
config.model_paths.Wan_2_1.t5_path

# 内部实现：ModelPaths._data 是普通字典
# __getattr__ 自动返回嵌套的 _DictWrapper
```

**Schema Manager：**

`ModelPathsSchemaManager` 从训练模型注册表初始化 schema，提供：
- `get_schema()` - 获取前端需要的字段定义
- `get_valid_paths()` - 获取所有有效的配置路径
- `clean_config()` - 按 schema 清理配置（移除无效字段）

启动时自动扫描所有已注册模型的 `path_mapping`，生成动态 schema。

**配置文件示例：**

```json
{
  "model_paths": {
    "qwen_image": {
      "dit_path": "/path/to/dit",
      "vae_path": "/path/to/vae",
      "text_encoder_path": "/path/to/te"
    },
    "flux_kontext": {
      "dit_path": "/path/to/dit",
      "vae_path": "/path/to/vae",
      "text_encoder1_path": "/path/to/t5",
      "text_encoder2_path": "/path/to/clip"
    },
    "Wan_2_1": {
      "dit_path": "/path/to/dit",
      "vae_path": "/path/to/vae",
      "t5_path": "/path/to/t5"
    },
    "Wan_2_2": {
      "dit_path": "/path/to/dit",
      "vae_path": "/path/to/vae",
      "t5_path": "/path/to/t5"
    }
  },
  "labeling": {
    "default_prompt": "...",
    "translation_prompt": "...",
    "selected_model": "lm_studio",
    "delay_between_calls": 2.0,
    "models": {
      "gpt": { "enabled": false, "api_key": "", ... },
      "lm_studio": { "enabled": true, "base_url": "http://127.0.0.1:1234/v1", ... },
      "local_qwen_vl": { "enabled": false, ... }
    }
  },
  "training": {
    "default_epochs": 16,
    "default_batch_size": 2,
    "default_learning_rate": 0.0001,
    "default_resolution": "1024,1024",
    "memory_presets": {
      "low": { "fp8_base": true, "fp8_scaled": true, "blocks_to_swap": 45 },
      "medium": { "fp8_base": true, "fp8_scaled": true, "blocks_to_swap": 16 },
      "high": { "fp8_base": false, "fp8_scaled": false, "blocks_to_swap": 0 }
    }
  },
  "storage": {
    "workspace_root": "./workspace",
    "datasets_dir": "datasets",
    "cache_dir": "cache",
    "models_dir": "models",
    "medium_max_side": 1280,
    "preview_max_side": 512
  }
}
```

---

### 5. 前端架构

**技术栈：**
- React 18 + TypeScript
- Vite (构建工具)
- HeroUI (UI 组件库)
- TanStack Router (路由)

**核心页面：**
- `/` - 数据集列表 (`DatasetsList.tsx`)
- `/datasets/:id` - 数据集详情 (`DatasetDetail.tsx`)
- `/training` - 训练任务列表 (未实现)
- `/settings` - 设置页 (`Settings.tsx`)

**模型路径分组显示（前端）：**

前端使用 `modelGrouping.ts` 工具自动分组显示模型路径：

```typescript
// 分组规则：按 type_name 的下划线前缀分组
// qwen_image, qwen_image_edit → qwen 组
// Wan_2_1, Wan_2_2 → wan 组
// flux_kontext → flux 组

// 共享字段：vae_path, text_encoder_path, text_encoder1_path,
//           text_encoder2_path, clip_path, t5_path
// 独占字段：dit_path, unet_path

// 保存时：修改共享字段会同时更新该组所有模型
// 显示时：共享字段只显示一次（从第一个模型读取）
```

**设置页布局：**
```
模型路径设置
├── Qwen 系列
│   ├── VAE 模型路径 (共享)
│   ├── 文本编码器路径 (共享)
│   ├── Qwen-Image LoRA - DiT 模型路径 (独占)
│   └── Qwen-Image Edit LoRA - DiT 模型路径 (独占)
├── Flux 系列
│   ├── VAE 模型路径 (共享)
│   ├── 文本编码器路径 (T5-XXL) (共享)
│   ├── 文本编码器路径 (CLIP-L) (共享)
│   └── Flux Kontext LoRA - DiT 模型路径 (独占)
└── Wan 系列
    ├── VAE 模型路径 (共享)
    ├── T5-XXL 模型路径 (共享)
    ├── Wan2.1 - Wan2.1 模型路径 (独占)
    └── Wan2.2 - DiT 模型路径 (独占)
```

---

## 关键技术实现

### 1. 异步缩略图生成

使用 `asyncio.create_task()` 在后台异步生成缩略图，避免阻塞主线程：

```python
# dataset_service.py
async def add_images_to_dataset(...):
    # 保存原图
    save_original_image(...)

    # 异步生成缩略图（不等待）
    asyncio.create_task(self._generate_thumbnails_async(image_path, ...))

    return image_info  # 立即返回
```

### 2. WebSocket 日志推送

训练日志通过 WebSocket 实时推送到前端：

```python
# backend/app/api/websocket.py
@router.websocket("/ws/training/{task_id}")
async def training_websocket(websocket: WebSocket, task_id: str):
    await websocket.accept()

    # 订阅日志流
    async for log_line in training_service.stream_logs(task_id):
        await websocket.send_json({
            "type": "log",
            "data": log_line
        })
```

### 3. TensorBoard 事件解析

实时解析 TensorBoard 事件文件，提取训练指标：

```python
# backend/app/services/tb_event_service.py
def parse_tensorboard_events(log_dir: str) -> List[Metric]:
    metrics = []
    for event in tf.train.summary_iterator(tfevents_path):
        for value in event.summary.value:
            metrics.append({
                "step": event.step,
                "tag": value.tag,
                "value": value.simple_value
            })
    return metrics
```

### 4. 动态 Provider 加载

打标系统使用 Provider 模式，支持动态加载：

```python
# providers/__init__.py
def load_providers():
    provider_dir = Path(__file__).parent
    for file in provider_dir.glob("*.py"):
        if file.stem.startswith("_"):
            continue
        module = importlib.import_module(f".{file.stem}", package=__package__)
        # 自动注册实现了 BaseProvider 的类

# ai_client.py
def create_client(provider_type: str, config: APIModelConfig):
    provider_class = PROVIDER_REGISTRY[provider_type]
    return provider_class(config)
```

---

## 常见问题

### Q1: 如何添加新的训练模型？

在 `backend/app/core/training/models.py` 中：

1. 定义配置类（继承 `BaseTrainingConfig`）
2. 调用 `register_model()` 注册模型
3. 重启后端，`schema_manager` 会自动扫描并生成 schema
4. 前端自动显示新模型的配置项

### Q2: 如何添加新的打标 Provider？

在 `backend/app/core/labeling/providers/` 中：

1. 创建新文件，如 `my_provider.py`
2. 实现 `BaseProvider` 接口
3. 在 `__init__.py` 中注册到 `PROVIDER_REGISTRY`
4. 在配置中添加对应的 `APIModelConfig`

### Q3: 模型路径配置的保存和读取流程？

**保存流程：**
1. 前端用户在设置页输入路径
2. 前端调用 `PUT /api/v1/settings`
3. 后端 `schema_manager.clean_config()` 清洗配置
4. 保存到 `config.json`

**读取流程（创建训练任务）：**
1. 用户创建训练任务，选择模型类型（如 `qwen_image`）
2. TrainingManager 查找 `ModelSpec`
3. 遍历 `path_mapping`，从配置文件读取路径
4. 填充到配置类实例（如 `QwenImage`）
5. 生成训练命令行参数

### Q4: 前端如何实现模型路径分组？

使用 `web/src/utils/modelGrouping.ts`：

- `getModelGroupKey()` - 按下划线前缀分组
- `isSharedField()` - 判断是否为共享字段
- `buildModelGroups()` - 构建分组数据
- `setGroupedValue()` - 保存时同时更新组内所有模型

**关键逻辑：**
```typescript
// 保存共享字段时，同时更新该组所有模型
if (isSharedField(fieldKey)) {
  for (const model of allModelsInGroup) {
    const path = `model_paths.${model.typeName}.${fieldKey}`;
    setNestedValue(settings, path, value);
  }
}
```

---

## 开发规范

1. **命名约定：**
   - 训练模型 type_name：使用下划线分隔（如 `qwen_image`，不要用点号）
   - path_mapping 左边键：必须和配置类字段名一致
   - path_mapping 右边值：config.json 中的存储路径

2. **配置类字段 metadata：**
   - `group`: 参数分组
   - `label`: UI 显示标签
   - `widget`: UI 组件类型
   - `help`: 提示信息
   - `cli`: CLI 参数映射（`name`, `type`, `formatter`）
   - `ui_hidden`: 是否隐藏
   - `persist`: 是否持久化

3. **共享字段约定：**
   - VAE、Text Encoder、CLIP 等权重路径视为共享字段
   - DiT、UNet 等核心模型路径视为独占字段

---

## 项目启动

**后端：**
```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

**前端：**
```bash
cd web
pnpm install
pnpm dev
```

**访问地址：**
- 前端：http://localhost:5173
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs

---

## 重要提示

1. **musubi-tuner 是 Git Submodule**，需要单独初始化：
   ```bash
   git submodule update --init --recursive
   ```

2. **配置文件路径**：`backend/config/config.json`

3. **工作空间路径**：`workspace/` （数据集、缓存、模型输出）

4. **所有与 AI、Claude 或技术支持的交流必须使用中文。**

---

**最后更新：** 2025-10-04
