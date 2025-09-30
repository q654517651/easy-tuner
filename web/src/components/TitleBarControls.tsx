import * as React from "react";
import IconClose from "../assets/icon/icon_close.svg?react";
import IconMaximize from "../assets/icon/icon_maximize.svg?react";
import IconMinimize from "../assets/icon/icon_minimize.svg?react";

export default function TitleBarControls() {
  const [maxed, setMaxed] = React.useState(false);
  const [focused, setFocused] = React.useState(true);
  // 立即同步检测Electron环境，避免异步设置导致的闪烁
  const [isElectron, setIsElectron] = React.useState(() =>
    typeof window !== 'undefined' && window.navigator.userAgent.includes('Electron')
  );

  React.useEffect(() => {
    // 检测是否在Electron环境中
    const electronEnv = window.navigator.userAgent.includes('Electron');
    setIsElectron(electronEnv);

    if (!electronEnv) return;

    let unsub = () => {};
    (async () => {
      try {
        const [m, f] = await Promise.all([
          window.winCtrl?.isMaximized?.() ?? Promise.resolve(false),
          window.winCtrl?.isFocused?.() ?? Promise.resolve(true),
        ]);
        setMaxed(m);
        setFocused(f);
      } catch {}

      // 订阅窗口状态变化
      if (window.winCtrl?.onMaximizeChanged) {
        unsub = window.winCtrl.onMaximizeChanged((m) => setMaxed(m));
      }
    })();
    return () => unsub();
  }, []);

  // 在非Electron环境中不显示标题栏
  if (!isElectron) {
    return null;
  }

  const btnCls = (extra = "") =>
    `ttb-btn ${!focused ? "ttb-btn--unfocused" : ""} ${extra}`;

  return (
    <div
      className="ttb-bar"
      style={{ WebkitAppRegion: "drag" } as any}
      onDoubleClick={() => window.winCtrl?.maximizeToggle?.()}
      role="banner"
      aria-label="Window title bar"
    >
      {/* 右：窗口控制按钮 */}
      <div className="ttb-right" style={{ WebkitAppRegion: "no-drag" } as any}>
        <button
          className={btnCls("ttb-min")}
          aria-label="Minimize"
          onClick={() => window.winCtrl?.minimize?.()}
        >
          <IconMinimize />
        </button>

        <button
          className={btnCls("ttb-max")}
          aria-label={maxed ? "Restore" : "Maximize"}
          onClick={() => window.winCtrl?.maximizeToggle?.()}
        >
          <IconMaximize />
        </button>

        <button
          className={btnCls("ttb-close")}
          aria-label="Close"
          onClick={() => window.winCtrl?.close?.()}
        >
          <IconClose />
        </button>
      </div>
    </div>
  );
}