# 🚀 快速发布 v0.0.1 版本

## 一键执行命令

在项目根目录依次执行以下命令：

```bash
# 1. 提交所有更改
git add .
git commit -m "chore: release v0.0.1"

# 2. 创建标签
git tag -a v0.0.1 -m "Release v0.0.1 - 首个正式版本"

# 3. 推送（触发自动构建）
git push origin master
git push origin v0.0.1
```

## 监控构建

访问：https://github.com/q654517651/easy-tuner/actions

等待 **15-20 分钟** 构建完成。

## 查看结果

访问：https://github.com/q654517651/easy-tuner/releases

应该能看到：
- ✅ EasyTuner Setup 0.0.1.exe
- ✅ EasyTuner Setup 0.0.1.exe.blockmap
- ✅ latest.yml

## 发布前检查

- [ ] 版本号是 `0.0.1`（在 `web/package.json`）
- [ ] GitHub Actions 已启用
- [ ] Workflow 权限设为 "Read and write"

检查方法：
https://github.com/q654517651/easy-tuner/settings/actions

## 如果构建失败

```bash
# 删除标签
git tag -d v0.0.1
git push origin :refs/tags/v0.0.1

# 修复问题后重新发布
git tag -a v0.0.1 -m "Release v0.0.1"
git push origin v0.0.1
```

## 详细指南

查看完整发布指南：[docs/RELEASE_V0.0.1_GUIDE.md](./docs/RELEASE_V0.0.1_GUIDE.md)

---

**就是这么简单！** 🎉

