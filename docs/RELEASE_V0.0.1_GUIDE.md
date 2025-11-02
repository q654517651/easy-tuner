# 发布 v0.0.1 版本指南

这是你的第一个正式版本发布！本指南将一步步指导你完成整个发布流程。

## 📋 发布前检查清单

### 1. 确认本地环境

- [ ] Python 3.11 已安装
- [ ] Node.js 20+ 已安装
- [ ] pnpm 8+ 已安装
- [ ] 已创建虚拟环境 `.venv`
- [ ] Git 配置正常

### 2. 确认代码状态

- [ ] 所有功能已完成并测试
- [ ] 没有明显的 bug
- [ ] 代码已全部提交到本地仓库
- [ ] 版本号已正确设置为 `0.0.1`（在 `web/package.json` 中）

### 3. 确认 GitHub 仓库设置

访问：https://github.com/q654517651/easy-tuner/settings/actions

检查：
- [ ] Actions 已启用（`Settings > Actions > General > Actions permissions` 设为 "Allow all actions"）
- [ ] Workflow 权限设为 "Read and write permissions"（`Settings > Actions > General > Workflow permissions`）

## 🚀 发布步骤

### 步骤 1：本地构建测试（可选但推荐）

在发布到 GitHub 之前，先在本地测试一次完整构建：

```powershell
# 在项目根目录执行
.\build-all.ps1
```

**预期结果**：
- 后端构建成功：`backend/dist/EasyTunerBackend.exe`
- 前端构建成功：`web/dist/` 包含安装包

**如果构建失败**：
- 检查错误日志
- 修复问题后重新测试
- 不要继续发布流程

### 步骤 2：确认版本号

检查 `web/package.json` 中的版本号：

```json
{
  "version": "0.0.1"
}
```

**重要**：确认版本号是 `0.0.1`，不是其他值。

### 步骤 3：提交所有更改

```bash
# 查看当前状态
git status

# 添加所有更改
git add .

# 提交（使用语义化提交信息）
git commit -m "chore: release v0.0.1

- 初始版本发布
- 支持基本的数据集管理和标注功能
- 集成自动更新功能
"

# 推送到远程仓库
git push origin master
```

### 步骤 4：创建并推送标签

**这是触发自动构建的关键步骤！**

```bash
# 创建标签（必须以 v 开头）
git tag -a v0.0.1 -m "Release version 0.0.1

首个正式版本，包含以下功能：
- ✅ 基本的打标功能包括单图打标与批量打标
- ✅ 基本的标签管理功能包括增删标签与调换位置
- ✅ 基本的图片裁剪功能，可将不同尺寸比例的图片调整为统一尺寸
- ✅ 基本的训练管理功能，包括开启训练终止训练完成训练
- ✅ Electron 自动更新支持
"

# 推送标签到远程仓库（触发 GitHub Actions）
git push origin v0.0.1
```

**💡 小贴士**：`-a` 参数创建带注释的标签，这样 GitHub Release 会显示标签信息。

### 步骤 5：监控构建过程

推送标签后，立即访问：
https://github.com/q654517651/easy-tuner/actions

你会看到一个新的 workflow run：
- 名称：**Release App**
- 触发者：你的 GitHub 账号
- 触发事件：push v0.0.1

**构建阶段**：
1. ⏳ **检出代码** (30 秒)
2. ⏳ **设置 Python 3.11** (1 分钟)
3. ⏳ **创建 Python 虚拟环境** (1 分钟)
4. ⏳ **安装 Python 依赖** (2-3 分钟)
5. ⏳ **构建后端 (PyInstaller)** (3-5 分钟)
6. ⏳ **设置 Node.js** (1 分钟)
7. ⏳ **安装 pnpm** (30 秒)
8. ⏳ **安装前端依赖** (2-3 分钟)
9. ⏳ **构建前端并打包 Electron** (5-8 分钟)
10. ⏳ **上传构建产物到 Release** (1-2 分钟)

**总耗时**：约 **15-20 分钟**

### 步骤 6：检查构建结果

#### 如果构建成功 ✅

你会看到：
- 所有步骤都显示绿色勾号 ✓
- 最后一步 "上传构建产物到 Release" 完成

访问 Release 页面：
https://github.com/q654517651/easy-tuner/releases

你应该能看到：
- **Release 标题**：v0.0.1
- **Release 说明**：自动生成或你的标签注释
- **Assets（资产文件）**：
  - `EasyTuner Setup 0.0.1.exe` - Windows 安装包（约 200-400 MB）
  - `EasyTuner Setup 0.0.1.exe.blockmap` - 增量更新文件
  - `latest.yml` - 自动更新配置文件

#### 如果构建失败 ❌

点击失败的步骤查看错误日志：

**常见问题**：

1. **后端构建失败**
   - 原因：依赖缺失或 PyInstaller 配置错误
   - 解决：检查 `backend/requirements.txt` 和构建日志

2. **前端构建失败**
   - 原因：依赖冲突或 TypeScript 错误
   - 解决：在本地运行 `cd web && pnpm build` 查看详细错误

3. **后端 EXE 未找到**
   - 原因：PyInstaller 构建没有生成 EXE
   - 解决：检查后端构建步骤的日志

4. **上传失败**
   - 原因：权限不足或文件路径错误
   - 解决：检查 GitHub Actions 权限设置

**如何重试**：
```bash
# 删除本地和远程标签
git tag -d v0.0.1
git push origin :refs/tags/v0.0.1

# 修复问题后，重新创建和推送标签
git tag -a v0.0.1 -m "Release version 0.0.1"
git push origin v0.0.1
```

### 步骤 7：测试安装包

下载刚发布的安装包：

```
https://github.com/q654517651/easy-tuner/releases/download/v0.0.1/EasyTuner.Setup.0.0.1.exe
```

**测试清单**：
- [ ] 安装程序可以正常运行
- [ ] 应用可以正常启动
- [ ] 后端服务正常加载
- [ ] 主要功能正常工作：
  - [ ] 创建数据集
  - [ ] 上传图片
  - [ ] 标注功能
  - [ ] 图片裁剪
  - [ ] 训练任务创建
- [ ] 没有明显的崩溃或错误

### 步骤 8：编辑 Release 说明（可选）

访问：https://github.com/q654517651/easy-tuner/releases/tag/v0.0.1

点击 "Edit release" 按钮，添加更详细的说明：

```markdown
# EasyTuner v0.0.1 - 首个正式版本 🎉

这是 EasyTuner 的第一个正式发布版本！

## ✨ 主要功能

### 数据集管理
- 支持图像数据集、视频数据集、控制图像数据集
- 拖拽上传文件
- 数据集信息查看和编辑

### 智能标注
- 单图标注功能
- 批量 AI 标注（支持多种模型）
- 标签管理和排序
- 实时保存

### 图片处理
- 交互式图片裁剪
- 批量裁剪
- 多种尺寸预设

### 训练管理
- 可视化训练配置
- 实时训练进度监控
- GPU 利用率监控
- 训练日志查看

### 应用特性
- 现代化的用户界面
- 深色模式支持
- Electron 桌面应用
- 自动更新支持 🆕

## 📥 下载安装

**Windows 用户**：
下载 `EasyTuner Setup 0.0.1.exe` 并运行安装。

**系统要求**：
- Windows 10/11（64 位）
- 8GB+ 内存
- NVIDIA GPU（可选，用于训练和 GPU 监控）

## 🐛 已知问题

- 暂无

## 📝 更新日志

完整更新日志请查看：[CHANGELOG.md](https://github.com/q654517651/easy-tuner/blob/master/docs/CHANGELOG.md)

## 🙏 致谢

感谢所有贡献者和用户的支持！

---

**下一个版本计划**：v0.0.2
- 支持更多 AI 标注模型
- 添加多语言支持
- 优化性能和稳定性
```

保存后，Release 说明会更新。

## 🎉 发布完成！

恭喜！你已经成功发布了第一个版本。

### 下一步

1. **宣传发布**：
   - 在社交媒体分享
   - 更新项目 README
   - 通知用户和测试者

2. **收集反馈**：
   - 监控 GitHub Issues
   - 收集用户反馈
   - 记录 bug 和改进建议

3. **准备下一版本**：
   - 创建 v0.0.2 的开发分支
   - 规划新功能
   - 修复已知问题

## 📊 监控和维护

### 持续监控

- **GitHub Actions**：https://github.com/q654517651/easy-tuner/actions
- **Release 页面**：https://github.com/q654517651/easy-tuner/releases
- **Issues 页面**：https://github.com/q654517651/easy-tuner/issues

### 版本更新频率建议

- **修订版本（0.0.x）**：bug 修复，每 1-2 周
- **次版本（0.x.0）**：新功能，每 1-2 个月
- **主版本（x.0.0）**：重大变更，根据需要

## 🔗 相关文档

- [详细发布指南](./GITHUB_RELEASE_GUIDE.md)
- [快速开始](./AUTO_UPDATE_QUICKSTART.md)
- [项目协作指南](./AGENTS.md)

## 💬 需要帮助？

如有问题，请：
1. 查看文档：https://github.com/q654517651/easy-tuner/tree/master/docs
2. 提交 Issue：https://github.com/q654517651/easy-tuner/issues
3. 发送邮件：654517651@qq.com

---

祝你发布顺利！🚀

Git 常用命令大全（实战版）
一、版本标签（tag）管理
📌 添加版本号
# 创建轻量标签（仅记录当前提交）
git tag v0.0.3

# 或带注释（推荐）
git tag -a v0.0.3 -m "Release v0.0.3: 初始稳定版本"

🚀 推送标签到远端
# 推送单个版本
git push origin v0.0.3

# 推送所有未同步的标签
git push origin --tags

🗑 删除本地标签
git tag -d v0.0.1
git tag -d v0.0.2

🌐 删除远端标签
# 两种等价写法
git push origin --delete tag v0.0.1
git push origin :refs/tags/v0.0.2

🧾 查看标签
git tag
git show v0.0.3

git add .

git commit -m "修复日志重复"

git push origin master