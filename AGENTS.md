# 仓库协作指南（中文）

本文件为代理（AI 助手）与人类协作者在本仓库中的协作约定。除非系统/开发者/用户有更高优先级的直接指令，否则代理在本仓库及其子目录内遵循以下规则。

## 语言与沟通
- 默认使用中文进行所有交流与书写，包括回答问题、变更说明、代码评审意见、文档与注释。
- 如需使用特定语言（例如代码、配置、接口契约），应按需使用该语言；但说明性文字与交流仍以中文为主。
- 若上级指令与本规定冲突，以上级指令为准；若子目录存在更具体的 `AGENTS.md`，则以就近的文件为准。

## 项目结构与模块组织
- `backend/` — FastAPI 后端。入口：`backend/startup.py`；应用代码位于 `backend/app/{api,v1,core,services,models,utils}`。对外提供静态工作区 `/workspace`，WebSocket 位于 `/ws`。
- `web/` — React + TypeScript（Vite）。源码在 `web/src`，配置在 `web/package.json`、`web/vite.config.ts`。
- `src/easytuner/` — 早期 Flet 桌面实现（仅供参考；新功能请勿在此目录修改）。
- `assets/` 字体/图标；`runtime/` 为第三方引擎/工具的供应商目录（不可变更）；`test/` 为历史 UI 演示与样例。

## 构建、测试与开发命令
- 后端环境（Windows）：`py -3.11 -m venv .venv && .\.venv\Scripts\activate && pip install -r backend/requirements.txt`
  - 启动 API（热重载）：`python backend/startup.py`
  - 备选：`uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000`
- 前端：`cd web && pnpm install && pnpm dev`（构建：`pnpm build`，代码检查：`pnpm lint`，预览：`pnpm preview`）。
- 旧版 Flet 演示（可选）：`python test_side_bar.py`。

## 代码风格与命名约定
- Python（后端）：4 空格缩进，使用类型注解；函数/变量用 `snake_case`，类名用 `PascalCase`。日志使用 `backend/app/utils/logger.py`，避免使用 `print`。
- API：版本路径为 `/api/v1/*`；资源名称使用复数；正确使用 HTTP 状态码（创建用 201，删除用 204）。
- React/TS（前端）：2 空格缩进，使用函数式组件；组件文件 `PascalCase.tsx`，自定义 Hook 为 `useX.ts`。`web/` 已配置 ESLint。

## 测试规范
- 后端：优先使用 `pytest`；测试放在 `backend/tests/test_*.py`。快速冒烟可执行：`python backend/test_simple.py`。
- 前端：通过 `pnpm dev` 手动验证；UI 变更请附带截图或 GIF。

## 提交与 Pull Request 规范
- 遵循 Conventional Commits：`feat:`、`fix:`、`docs:`、`refactor:`、`test:`、`chore:`。
- PR 内容应简洁明了，包含关联问题与复现步骤；UI 变更附截图，API/训练相关变更请附日志或配置示例。保持 PR 聚焦，并在行为变更时更新相关文档/示例。

## 安全与配置提示
- 切勿提交任何密钥。外部模型/服务使用环境变量（如 `OPENAI_API_KEY`、`ANTHROPIC_API_KEY`）。
- 开发环境 CORS 允许来源：`http://localhost:5173`。后端默认运行在 `127.0.0.1:8000`。
- 将 `runtime/` 视为供应商目录且不可在 PR 中修改。
