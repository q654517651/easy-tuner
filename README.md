# EasyTuner

<div align="center">

[中文](#中文) | [English](#english)

一个功能强大的 AI 模型训练数据集管理与标注工具

A powerful dataset management and labeling tool for AI model training

![Version](https://img.shields.io/badge/version-0.0.1-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

</div>

---

# 中文

## 📖 项目简介

EasyTuner 是一个专为 AI 模型训练设计的数据集管理和标注工具，提供直观的可视化界面和完整的工作流支持。从数据集创建、图像标注、批量处理到训练任务管理，帮助您更高效地准备训练数据。

### ✨ 核心特性

- 🗂️ **多类型数据集支持**
  - 图像数据集（Image Dataset）
  - 视频数据集（Video Dataset）
  - 单控制图数据集（Single Control Image）
  - 多控制图数据集（Multi Control Image）

- 🏷️ **智能标注系统**
  - AI 自动打标（支持多种模型）
  - 批量打标功能
  - 拖拽式标签管理
  - 实时保存，无需手动保存

- ✂️ **图像处理**
  - 交互式图片裁剪
  - 批量裁剪处理
  - 实时预览

- 🚀 **训练任务管理**
  - 可视化训练配置
  - 实时训练进度监控
  - TensorBoard 集成
  - GPU 使用率监控
  - 训练日志查看

- 💻 **现代化界面**
  - 响应式设计
  - 深色模式支持
  - 拖拽上传文件
  - 实时 WebSocket 通信
  - 流畅的动画效果

## 🏗️ 技术架构

### 前端
- **框架**: React 19 + TypeScript
- **构建工具**: Vite
- **UI 库**: HeroUI (基于 Tailwind CSS)
- **路由**: React Router v7
- **状态管理**: React Hooks
- **拖拽**: @dnd-kit
- **图表**: uPlot
- **桌面应用**: Electron

### 后端
- **框架**: FastAPI
- **异步运行时**: Uvicorn
- **数据验证**: Pydantic
- **图像处理**: Pillow + NumPy
- **GPU 监控**: pynvml
- **日志**: Loguru
- **WebSocket**: websockets

## 📦 安装与运行

### 前置要求

- Python 3.11+
- Node.js 18+
- pnpm 8+
- NVIDIA GPU（可选，用于训练和 GPU 监控）

### 开发环境搭建

#### 1. 克隆仓库

```bash
git clone <repository-url>
cd tagtragger
```

#### 2. 后端设置

```bash
# 创建虚拟环境
py -3.11 -m venv .venv

# 激活虚拟环境（Windows）
.\.venv\Scripts\activate

# 安装依赖
pip install -r backend/requirements.txt

# 启动后端服务
python backend/startup.py
```

后端将在 `http://127.0.0.1:8000` 运行

#### 3. 前端设置

```bash
# 进入前端目录
cd web

# 安装依赖
pnpm install

# 启动开发服务器
pnpm dev
```

前端将在 `http://localhost:5173` 运行

### 生产环境构建

#### 构建 Web 应用

```bash
cd web
pnpm build:web
```

#### 构建桌面应用

```bash
cd web
pnpm dist
```

生成的安装包位于 `web/dist/` 目录

## 🎯 使用指南

### 1. 创建数据集

1. 点击"数据集"标签
2. 点击"新建数据集"按钮
3. 选择数据集类型（图像/视频/控制图）
4. 输入数据集名称
5. 拖拽文件或点击上传

### 2. 标注数据

**单张标注**：
- 选择数据集进入详情页
- 在"打标"标签页中查看图片
- 点击图片下方的标注区域输入标签
- 标签自动保存

**批量 AI 标注**：
- 勾选需要标注的图片
- 点击"批量打标"按钮
- 等待 AI 自动完成标注

**标签管理**：
- 切换到"标签管理"标签页
- 拖拽调整标签顺序
- 双击编辑标签内容
- 点击删除按钮移除标签

### 3. 图片裁剪

1. 在图像数据集中切换到"图片裁剪"标签
2. 设置目标尺寸（宽 × 高）
3. 拖拽和缩放调整裁剪区域
4. 点击"确认裁剪"批量处理

### 4. 创建训练任务

1. 点击"训练"标签
2. 点击"新建训练"按钮
3. 选择训练类型和数据集
4. 配置训练参数
5. 点击"开始训练"

### 5. 监控训练

- 实时查看训练步数、损失、速度
- GPU 使用率和温度监控
- TensorBoard 可视化
- 训练日志实时输出
- 查看生成的样本图片

## 📁 项目结构

```
tagtragger/
├── backend/                 # 后端服务
│   ├── app/
│   │   ├── api/            # API 路由
│   │   ├── core/           # 核心业务逻辑
│   │   ├── models/         # 数据模型
│   │   ├── services/       # 业务服务层
│   │   └── utils/          # 工具函数
│   ├── scripts/            # 辅助脚本
│   └── startup.py          # 启动入口
├── web/                    # 前端应用
│   ├── electron/           # Electron 主进程
│   ├── src/
│   │   ├── components/     # React 组件
│   │   ├── pages/          # 页面组件
│   │   ├── services/       # API 服务
│   │   ├── ui/             # UI 组件库
│   │   └── utils/          # 工具函数
│   └── package.json
├── workspace/              # 工作区（数据集、模型、任务）
│   ├── datasets/           # 数据集存储
│   ├── runtime/            # 运行时环境
│   └── tasks/              # 训练任务
└── assets/                 # 静态资源
```

## 🔧 配置说明

### 后端配置

后端配置位于 `backend/app/core/config.py`，主要配置项：

- `API_HOST`: API 服务器地址（默认：127.0.0.1）
- `API_PORT`: API 服务器端口（默认：8000）
- `WORKSPACE_ROOT`: 工作区根目录路径
- `LOG_LEVEL`: 日志级别

### 环境变量

可以创建 `.env` 文件设置环境变量：

```env
# AI 标注模型 API Keys
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# 其他配置
LOG_LEVEL=INFO
```

## 当前版本内容

### V0.0.1
- [√] 基本的打标功能包括单图打标与批量打标
- [√] 基本的标签管理功能包括增删标签与调换位置
- [√] 基本的图片裁剪功能，可将不同尺寸比例的图片调整为统一尺寸
- [√] 基本的训练管理功能，包括开启训练终止训练完成训练

### 未来的计划
- [ ] 支持更多 AI 标注模型
- [ ] 测试wan2.1,wan2.2等训练效果
- [ ] 添加多语言支持
- [ ] 添加数据集导出功能
- [ ] 支持linux等云服务平台部署
- [ ] 支持应用内自动更新



## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

- [FastAPI](https://fastapi.tiangolo.com/) - 现代化的 Python Web 框架
- [React](https://react.dev/) - 用户界面库
- [HeroUI](https://heroui.com/) - 美观的 React UI 库
- [Electron](https://www.electronjs.org/) - 跨平台桌面应用框架

## 📞 联系方式

- 问题反馈：654517651@qq.com, qq654517651@gmail.com

---

# English

## 📖 Introduction

EasyTuner is a dataset management and labeling tool designed for AI model training, providing an intuitive visual interface and complete workflow support. From dataset creation, image annotation, batch processing to training task management, it helps you prepare training data more efficiently.

### ✨ Key Features

- 🗂️ **Multi-type Dataset Support**
  - Image Dataset
  - Video Dataset
  - Single Control Image Dataset
  - Multi Control Image Dataset

- 🏷️ **Intelligent Labeling System**
  - AI-powered auto-labeling (multiple models supported)
  - Batch labeling functionality
  - Drag-and-drop tag management
  - Tag auto-completion and suggestions
  - Real-time saving, no manual save needed

- ✂️ **Image Processing**
  - Interactive image cropping
  - Batch cropping
  - Multiple size presets
  - Real-time preview

- 🚀 **Training Task Management**
  - Visual training configuration
  - Real-time training progress monitoring
  - TensorBoard integration
  - GPU utilization monitoring
  - Training log viewing

- 💻 **Modern Interface**
  - Responsive design
  - Dark mode support
  - Drag-and-drop file upload
  - Real-time WebSocket communication
  - Smooth animations

## 🏗️ Tech Stack

### Frontend
- **Framework**: React 19 + TypeScript
- **Build Tool**: Vite
- **UI Library**: HeroUI (based on Tailwind CSS)
- **Routing**: React Router v7
- **State Management**: React Hooks
- **Drag & Drop**: @dnd-kit
- **Charts**: uPlot
- **Desktop App**: Electron

### Backend
- **Framework**: FastAPI
- **Async Runtime**: Uvicorn
- **Data Validation**: Pydantic
- **Image Processing**: Pillow + NumPy
- **GPU Monitoring**: pynvml
- **Logging**: Loguru
- **WebSocket**: websockets

## 📦 Installation & Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- pnpm 8+
- NVIDIA GPU (optional, for training and GPU monitoring)

### Development Setup

#### 1. Clone Repository

```bash
git clone <repository-url>
cd tagtragger
```

#### 2. Backend Setup

```bash
# Create virtual environment
py -3.11 -m venv .venv

# Activate virtual environment (Windows)
.\.venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt

# Start backend server
python backend/startup.py
```

Backend will run at `http://127.0.0.1:8000`

#### 3. Frontend Setup

```bash
# Navigate to frontend directory
cd web

# Install dependencies
pnpm install

# Start development server
pnpm dev
```

Frontend will run at `http://localhost:5173`

### Production Build

#### Build Web Application

```bash
cd web
pnpm build:web
```

#### Build Desktop Application

```bash
cd web
pnpm dist
```

Installers will be generated in `web/dist/` directory

## 🎯 Usage Guide

### 1. Create Dataset

1. Click "Datasets" tab
2. Click "New Dataset" button
3. Select dataset type (Image/Video/Control Image)
4. Enter dataset name
5. Drag files or click to upload

### 2. Label Data

**Single Image Labeling**:
- Select a dataset to enter details page
- View images in "Labeling" tab
- Click annotation area below image to input tags
- Tags are auto-saved

**Batch AI Labeling**:
- Select images to label
- Click "Batch Label" button
- Wait for AI to complete labeling

**Tag Management**:
- Switch to "Tag Management" tab
- Drag to reorder tags
- Double-click to edit tag content
- Click delete button to remove tags

### 3. Image Cropping

1. Switch to "Image Cropping" tab in image dataset
2. Set target size (Width × Height)
3. Drag and zoom to adjust crop area
4. Click "Confirm Crop" to batch process

### 4. Create Training Task

1. Click "Training" tab
2. Click "New Training" button
3. Select training type and dataset
4. Configure training parameters
5. Click "Start Training"

### 5. Monitor Training

- Real-time view of training steps, loss, speed
- GPU utilization and temperature monitoring
- TensorBoard visualization
- Real-time training log output
- View generated sample images

## 📁 Project Structure

```
tagtragger/
├── backend/                 # Backend service
│   ├── app/
│   │   ├── api/            # API routes
│   │   ├── core/           # Core business logic
│   │   ├── models/         # Data models
│   │   ├── services/       # Business service layer
│   │   └── utils/          # Utility functions
│   ├── scripts/            # Helper scripts
│   └── startup.py          # Entry point
├── web/                    # Frontend application
│   ├── electron/           # Electron main process
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── pages/          # Page components
│   │   ├── services/       # API services
│   │   ├── ui/             # UI component library
│   │   └── utils/          # Utility functions
│   └── package.json
├── workspace/              # Workspace (datasets, models, tasks)
│   ├── datasets/           # Dataset storage
│   ├── runtime/            # Runtime environment
│   └── tasks/              # Training tasks
└── assets/                 # Static resources
```

## 🔧 Configuration

### Backend Configuration

Backend configuration is in `backend/app/core/config.py`, main settings:

- `API_HOST`: API server address (default: 127.0.0.1)
- `API_PORT`: API server port (default: 8000)
- `WORKSPACE_ROOT`: Workspace root directory path
- `LOG_LEVEL`: Logging level

### Environment Variables

Create a `.env` file to set environment variables:

```env
# AI Labeling Model API Keys
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# Other configurations
LOG_LEVEL=INFO
```

## Current Version Content

### V0.0.1
- [√] Basic labeling functionality including single image labeling and batch labeling
- [√] Basic tag management functionality including adding/deleting tags and reordering
- [√] Basic image cropping functionality to adjust images of different sizes to a uniform size
- [√] Basic training management functionality, including starting, stopping, and completing training

### Future Plans
- [ ] Support more AI labeling models
- [ ] Test training effects of wan2.1, wan2.2, etc.
- [ ] Add multilingual support
- [ ] Add dataset export functionality
- [ ] Support deployment on Linux and other cloud platforms
- [ ] Support in-app automatic updates

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [React](https://react.dev/) - User interface library
- [HeroUI](https://heroui.com/) - Beautiful React UI library
- [Electron](https://www.electronjs.org/) - Cross-platform desktop framework

## 📞 Contact

- Issue Reporting: 654517651@qq.com, qq654517651@gmail.com

---

<div align="center">

Made with ❤️ by the EasyTuner Team

</div>

