# 自动更新功能快速开始

## 🎯 快速发布新版本

### 三步发布流程

```bash
# 1. 修改版本号（web/package.json）
# "version": "0.0.2"

# 2. 提交并打标签
git add .
git commit -m "chore: release v0.0.2"
git tag v0.0.2

# 3. 推送（自动触发构建和发布）
git push origin master
git push origin v0.0.2
```

### 查看构建进度

访问：https://github.com/q654517651/easy-tuner/actions

构建时间约 **10-15 分钟**（Windows Runner + Python + Node.js）

## ✅ 功能验证

### 用户端体验

1. **安装旧版本** → 使用 v0.0.1 安装包
2. **启动应用** → 等待 5 秒
3. **收到通知** → "发现新版本 v0.0.2"
4. **下载更新** → 显示进度条
5. **安装更新** → 退出并自动安装

### 开发者检查清单

- [ ] GitHub Actions 构建成功（绿色勾）
- [ ] Release 页面有 3 个文件（.exe、.blockmap、latest.yml）
- [ ] 旧版本应用能检测到新版本
- [ ] 下载和安装流程正常
- [ ] 新版本正常启动

## 📁 核心文件

| 文件 | 作用 |
|------|------|
| `.github/workflows/release.yml` | 自动构建和发布 |
| `web/src/components/UpdateNotification.tsx` | 更新通知界面 |
| `web/electron/main.ts` | 自动更新逻辑 |
| `web/electron/preload.ts` | 更新 API 暴露 |
| `web/package.json` | 发布配置 |

## 🔍 调试技巧

### 查看更新日志

Electron 主进程会输出日志：

```
[updater] 正在检查更新...
[updater] 发现新版本: 0.0.2
[updater] 下载进度: 45.67%
[updater] 更新已下载，准备安装
```

### 手动触发检查

在开发者工具 Console 中：

```javascript
window.electron.updater.checkForUpdates()
```

### 跳过自动检查

如果不想等待 5 秒：

```javascript
// 在 main.ts 中修改超时时间
setTimeout(() => {
  autoUpdater.checkForUpdates();
}, 1000); // 改为 1 秒
```

## 🚨 注意事项

1. **版本号必须递增**：electron-updater 会比较版本号
2. **标签必须以 v 开头**：如 `v0.0.2`
3. **仅生产环境生效**：开发模式下自动跳过更新
4. **需要网络连接**：检查更新需要访问 GitHub API

## 📚 详细文档

查看完整文档：[GITHUB_RELEASE_GUIDE.md](./GITHUB_RELEASE_GUIDE.md)

## 🎉 完成！

恭喜！你的应用现在支持自动更新了 🚀

