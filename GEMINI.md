# TagTragger / EasyTuner - 开发者指南

**语言设置：** 请始终使用 **中文 (Chinese)** 回答所有问题、编写文档和注释代码。

## 项目概述
**TagTragger** (又名 **EasyTuner**) 是一个专为 AI 模型训练设计的强大数据集管理与标注工具，特别专注于 LoRA 模型。它提供了从数据集创建、图像标注到批量处理和训练任务管理的完整工作流。

## 技术栈

### 后端 (Backend)
*   **语言:** Python 3.11+
*   **框架:** FastAPI
*   **服务器:** Uvicorn (异步)
*   **数据验证:** Pydantic
*   **图像处理:** Pillow, NumPy
*   **GPU 监控:** pynvml
*   **WebSocket:** 使用 `websockets` 库进行实时更新（日志、训练进度）
*   **训练引擎:** `musubi-tuner` (作为子模块/外部脚本集成)

### 前端 (Frontend)
*   **框架:** React 19 + TypeScript
*   **构建工具:** Vite
*   **桌面封装:** Electron
*   **UI 库:** HeroUI (基于 Tailwind CSS)
*   **路由:** React Router v7
*   **状态管理:** React Hooks
*   **拖拽库:** `@dnd-kit`
*   **图表库:** `uPlot`

## 项目结构

```text
E:\Program\programlearn\tagtragger\
├── backend/                 # Python 后端 (FastAPI)
│   ├── app/
│   │   ├── api/             # API 路由 (v1, internal, websocket)
│   │   ├── core/            # 核心逻辑 (config, models, schemas)
│   │   │   ├── dataset/     # 数据集管理逻辑
│   │   │   ├── labeling/    # AI 标注逻辑 (Providers)
│   │   │   └── training/    # 训练逻辑 (ModelSpec, Manager)
│   │   ├── models/          # Pydantic 数据模型
│   │   ├── services/        # 业务服务层 (dataset, labeling, training)
│   │   └── utils/           # 工具函数 (files, logging, network)
│   ├── build.ps1            # 后端构建脚本
│   ├── requirements.txt     # Python 依赖
│   ├── serve.py             # 备用入口点
│   └── startup.py           # 主入口点
├── web/                     # 前端 (React + Electron)
│   ├── electron/            # Electron 主进程文件
│   ├── src/                 # React 源代码
│   │   ├── components/      # 可复用 UI 组件
│   │   ├── contexts/        # React Contexts (Theme, Readiness)
│   │   ├── layouts/         # 页面布局
│   │   ├── pages/           # 应用视图/页面
│   │   ├── services/        # 前端 API 服务 (Axios)
│   │   └── utils/           # 前端工具函数
│   ├── vite.config.ts       # Electron 的 Vite 配置
│   └── vite.config.web.ts   # 纯 Web 模式的 Vite 配置
├── workspace/               # 用户数据 (通常被 Git 忽略)
│   ├── datasets/            # 存储的数据集 (图像, 元数据, 标注)
│   ├── models/              # 训练模型输出
│   └── runtime/             # 训练引擎 (musubi-tuner)
└── assets/                  # 静态资源 (字体, 图标)
```

## 安装与运行

### 后端
1.  **环境:** 确保已安装 Python 3.11+。
2.  **虚拟环境:** `py -3.11 -m venv .venv` (推荐)。
3.  **安装依赖:** `pip install -r backend/requirements.txt`。
4.  **运行:** `python backend/startup.py`。
    *   服务器运行在 `http://127.0.0.1:8000`。
    *   API 文档: `http://127.0.0.1:8000/docs`。

### 前端
1.  **环境:** Node.js 18+, pnpm 8+。
2.  **安装依赖:** `cd web` 然后 `pnpm install`。
3.  **运行 (Electron):** `pnpm dev` (启动 Vite + Electron)。
    *   运行在 `http://localhost:5173`。
4.  **运行 (纯 Web):** `pnpm dev:web` (仅启动 Vite)。
    *   运行在 `http://0.0.0.0:6006`。

## 核心架构概念

### 1. 数据集管理 (Dataset Management)
*   **存储:** 数据集存储在 `workspace/datasets/{dataset_id}`。
*   **结构:**
    *   `images/`: 原始图像。
    *   `medium/`: 调整大小的版本 (最长边 1280)，用于显示。
    *   `preview/`: 缩略图 (最长边 512)。
    *   `captions/`: 包含图像标签的文本文件 (`.txt`)。
    *   `metadata.json`: 数据集配置和状态。
*   **异步处理:** 图像缩略图生成和处理通常是异步进行的，以避免阻塞 UI。

### 2. AI 标注系统 (AI Labeling System)
*   **Providers:** 使用 Provider 模式 (`backend/app/core/labeling/providers/`) 支持多种 AI 后端 (OpenAI, LM Studio, Local Qwen-VL)。
*   **动态加载:** Providers 在 `PROVIDER_REGISTRY` 中注册，并根据用户配置加载。
*   **配置:** 通过 `config.py` 中的 `LabelingConfig` 进行管理。

### 3. 训练系统 (Training System)
*   **ModelSpec:** 训练模型 (如 Qwen-Image, Flux Kontext) 在 `backend/app/core/training/models.py` 中使用 `ModelSpec` 定义。
*   **注册表:** 模型必须通过 `register_model()` 注册。
*   **路径映射:** 系统使用 `ModelSpec` 中的 `path_mapping` 字典将 UI 配置字段映射到底层的 `config.json` 路径。
*   **引擎:** 封装 `musubi-tuner` 脚本。根据 `ModelSpec` 配置动态生成参数。

### 4. 配置管理 (Configuration)
*   **文件:** `backend/config/config.json`。
*   **管理器:** `backend/app/core/config.py` 负责加载和管理配置。
*   **Schema:** `backend/app/core/schema_manager.py` 根据注册的模型动态生成前端所需的 JSON Schema，允许 UI 自动适应新的训练模型。

## 开发规范
*   **约定:** 遵循现有的 Pydantic 模型进行数据验证。使用 `Loguru` 进行日志记录。
*   **API:** 所有新端点应添加到 `backend/app/api/v1/` 并包含在主路由中。
*   **前端:** 为了保持一致性，请使用 `HeroUI` 组件。确保所有 API 调用都使用 `web/src/services/` 中的集中式服务层。
*   **异步:** 后端是完全异步的；确保正确等待 (await) IO 密集型操作（文件 I/O，网络）。