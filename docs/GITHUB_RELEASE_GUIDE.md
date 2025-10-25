# GitHub Release 自动更新指南

本项目已配置 GitHub Actions 自动构建和发布，以及 Electron 自动更新功能。

## 📦 功能概述

- ✅ 自动构建后端（PyInstaller）和前端（Electron）
- ✅ 自动发布到 GitHub Release
- ✅ 应用内自动检查更新
- ✅ 增量更新支持（节省下载流量）
- ✅ 用户友好的更新通知界面

## 🚀 发布新版本

### 1. 更新版本号

修改 `web/package.json` 中的版本号：

```json
{
  "version": "0.0.2"  // 从 0.0.1 改为 0.0.2
}
```

### 2. 提交更改并创建标签

```bash
# 提交所有更改
git add .
git commit -m "chore: bump version to 0.0.2"

# 创建并推送标签（必须以 v 开头）
git tag v0.0.2
git push origin master
git push origin v0.0.2
```

### 3. 自动构建和发布

推送标签后，GitHub Actions 会自动：
1. 构建 Python 后端（PyInstaller）
2. 构建前端并打包 Electron 应用
3. 创建 GitHub Release
4. 上传安装包和更新配置文件

查看构建进度：https://github.com/q654517651/easy-tuner/actions

### 4. 发布完成后

构建成功后，在 GitHub Release 页面可以看到：
- `EasyTuner Setup 0.0.2.exe` - 完整安装包
- `EasyTuner Setup 0.0.2.exe.blockmap` - 增量更新文件
- `latest.yml` - 更新配置文件

## 🔄 自动更新工作流程

### 用户端更新流程

1. **启动应用** → 5 秒后自动检查更新
2. **发现新版本** → 显示更新弹窗，包含版本号和更新日志
3. **用户确认** → 点击"立即下载"开始下载
4. **显示进度** → 实时显示下载进度和速度
5. **下载完成** → 提示用户"立即安装"或"稍后安装"
6. **安装更新** → 退出应用并自动安装新版本

### 更新检查逻辑

- **自动检查**：应用启动后 5 秒自动检查（仅生产环境）
- **手动检查**：可在设置页面添加"检查更新"按钮
- **开发模式**：开发环境下自动跳过更新检查

## 📋 文件清单

### 新增文件

```
.github/
  └── workflows/
      └── release.yml                         # GitHub Actions 工作流

web/
  ├── src/
  │   ├── components/
  │   │   └── UpdateNotification.tsx          # 更新通知组件
  │   └── types/
  │       └── electron.d.ts                   # TypeScript 类型定义
  └── package.json (已修改)                    # 添加发布配置

web/electron/
  ├── main.ts (已修改)                        # 添加自动更新逻辑
  └── preload.ts (已修改)                     # 添加更新 API

web/src/shell/
  └── AppShell.tsx (已修改)                   # 集成更新通知组件
```

## ⚙️ 配置说明

### package.json 发布配置

```json
{
  "build": {
    "publish": [
      {
        "provider": "github",
        "owner": "q654517651",
        "repo": "easy-tuner",
        "releaseType": "release"
      }
    ],
    "nsis": {
      "perMachine": false,              // 用户级安装（更新更容易）
      "differentialPackage": true       // 启用增量更新
    }
  }
}
```

### 环境变量

GitHub Actions 使用以下环境变量：
- `GITHUB_TOKEN` - 自动提供，用于发布 Release

## 🧪 测试更新功能

### 本地测试

1. 发布版本 `v0.0.1`
2. 使用 `v0.0.1` 安装包安装应用
3. 发布版本 `v0.0.2`
4. 启动 `v0.0.1` 应用
5. 等待 5 秒，应该会自动检测到 `v0.0.2`

### 测试检查清单

- [ ] 自动检查更新功能正常
- [ ] 更新弹窗正确显示版本号和更新日志
- [ ] 下载进度正确显示
- [ ] 下载完成后提示安装
- [ ] 安装成功后应用正常启动
- [ ] 版本号正确更新

## 🔧 手动检查更新

可以在设置页面添加"检查更新"按钮：

```tsx
import { Button } from '@heroui/react';

function SettingsPage() {
  const handleCheckUpdate = async () => {
    const result = await window.electron?.updater?.checkForUpdates();
    if (result?.error) {
      console.error('检查更新失败:', result.error);
    }
  };

  return (
    <Button onPress={handleCheckUpdate}>
      检查更新
    </Button>
  );
}
```

## 🐛 常见问题

### 1. 构建失败

**原因**：后端或前端构建错误
**解决**：查看 GitHub Actions 日志，修复构建错误后重新推送标签

### 2. 更新检测失败

**原因**：网络问题或 GitHub API 限制
**解决**：稍后重试，确保网络连接正常

### 3. 增量更新不生效

**原因**：`differentialPackage` 未启用或 `.blockmap` 文件缺失
**解决**：确保 `package.json` 中 `differentialPackage: true`

### 4. 开发环境提示不支持更新

**原因**：`app.isPackaged` 为 false
**解决**：这是正常行为，更新功能仅在生产环境（打包后）生效

## 📚 版本号规范

遵循语义化版本（SemVer）：

```
v主版本.次版本.修订号

v1.0.0 - 首个稳定版本
v1.1.0 - 新增功能（向后兼容）
v1.1.1 - Bug 修复
v2.0.0 - 重大变更（不向后兼容）
```

## 🔒 安全建议

1. **代码签名**（可选）：
   - 购买代码签名证书
   - 在 `package.json` 中配置 `certificateFile` 和 `certificatePassword`
   - 可以避免 Windows SmartScreen 警告

2. **私有仓库**：
   - 如果使用私有仓库，需要在 Actions 中配置 `GH_TOKEN`

3. **Release 权限**：
   - 确保 GitHub Actions 有 Release 写入权限
   - 在仓库设置中检查 `Settings > Actions > General > Workflow permissions`

## 📞 支持

如有问题，请提交 Issue：https://github.com/q654517651/easy-tuner/issues

