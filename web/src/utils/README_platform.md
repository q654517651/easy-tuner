# Platform Detection Utility (平台检测工具)

## 概述

`platform.ts` 提供了统一的 Electron 环境检测方法，替代了项目中多处重复的检测逻辑。

## 使用方法

### 1. 在 React 组件中使用

```tsx
import { useIsElectron } from '../utils/platform';

function MyComponent() {
  const isElectron = useIsElectron();

  return (
    <div className={isElectron ? 'electron-style' : 'web-style'}>
      {isElectron ? 'Running in Electron' : 'Running in Browser'}
    </div>
  );
}
```

### 2. 在非 React 代码中使用

```ts
import { isElectron } from '../utils/platform';

if (isElectron()) {
  // Electron 特定逻辑
  console.log('Running in Electron');
} else {
  // 浏览器特定逻辑
  console.log('Running in Browser');
}
```

## 检测机制

工具使用多重检测机制以确保可靠性（按优先级排序）：

1. **`process.versions.electron`** - 最可靠，Electron 注入的版本信息
2. **`window.navigator.userAgent`** - 备用方案，检查 UA 字符串
3. **`window.electronAPI`** - 额外检查，如果有暴露的 IPC API

## 已统一的文件

以下文件已更新使用统一的平台检测工具：

- ✅ `web/src/ui/Sidebar.tsx`
- ✅ `web/src/components/TitleBarControls.tsx`
- ✅ `web/src/shell/AppShell.tsx`
- ✅ `web/src/components/BackendLoader.tsx`
- ✅ `web/src/main.tsx`

## 旧代码模式（不推荐）

❌ **不要再使用这些方式：**

```ts
// 方式1：直接检查 User-Agent
const isElectron = window.navigator.userAgent.includes('Electron');

// 方式2：检查 electronAPI
const isElectron = window.electronAPI !== undefined;

// 方式3：检查 process.versions
const anyProcess: any = typeof process !== 'undefined' ? process : undefined;
const isElectron = anyProcess?.versions?.electron;
```

## 新代码模式（推荐）

✅ **统一使用：**

```ts
// React 组件中
import { useIsElectron } from '../utils/platform';
const isElectron = useIsElectron();

// 非 React 代码中
import { isElectron } from '../utils/platform';
if (isElectron()) { ... }
```

## 注意事项

- `useIsElectron()` 是一个 React Hook，只能在组件中使用
- `isElectron()` 是一个普通函数，可以在任何地方使用
- 两者内部使用相同的检测逻辑，确保结果一致
- 工具支持服务端渲染（SSR），在服务端始终返回 `false`

## 维护建议

如果需要添加新的平台检测逻辑（如检测操作系统、设备类型等），请在 `platform.ts` 中统一添加，避免分散在各个文件中。
