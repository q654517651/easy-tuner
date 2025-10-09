/**
 * 平台检测工具
 *
 * 提供统一的平台检测方法，避免项目中重复实现
 */

/**
 * 检测是否运行在 Electron 环境中
 *
 * 使用多重检测机制确保可靠性：
 * 1. process.versions.electron（最可靠，Electron 注入的版本信息）
 * 2. window.navigator.userAgent（备用方案）
 *
 * @returns {boolean} 是否为 Electron 环境
 */
export function isElectron(): boolean {
  if (typeof window === 'undefined') {
    return false;
  }

  try {
    // 优先检查 process.versions.electron（最可靠的方式）
    const anyProcess: any = typeof process !== 'undefined' ? (process as any) : undefined;
    if (anyProcess?.versions?.electron) {
      return true;
    }

    // 备用：检查 User-Agent
    if (window.navigator.userAgent.includes('Electron')) {
      return true;
    }

    // 额外检查：window.electronAPI（如果有暴露的 API）
    if ((window as any).electronAPI !== undefined) {
      return true;
    }

    return false;
  } catch {
    return false;
  }
}

/**
 * React Hook: 检测是否运行在 Electron 环境中
 *
 * 用于 React 组件中，支持服务端渲染（SSR）
 *
 * @returns {boolean} 是否为 Electron 环境
 */
export function useIsElectron(): boolean {
  // 使用懒初始化，避免 SSR 时出错
  const [isElectronEnv] = React.useState(() => isElectron());
  return isElectronEnv;
}

// 为了向后兼容，导出一个默认实例
import React from 'react';
