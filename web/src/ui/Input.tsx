import React from "react";
import ArrowLineUpDown from "@/assets/icon/ArrowLineUpDown.svg?react";
import { SelectMenu } from "@/ui/SelectMenu";


/* ========= 类型定义 ========= */
export type EnumItem = { label: string; value: any };

/* ========= UI 基元 ========= */

// 统一"控件外框"：高度 88，圆角 16，内文字 14
export const Tile: React.FC<React.PropsWithChildren<{ className?: string }>> = ({ className, children }) => (
  <div
    className={
      "relative h-[88px] rounded-2xl bg-white ring-1 ring-black/10 px-4 " + (className || "")
    }
  >
    {children}
  </div>
);

// 浮动标签（淡灰 14）
export const FloatingLabel: React.FC<{ text: string }> = ({ text }) => (
  <div className="text-[14px] text-black/40 leading-[28px]" >{text}</div>
);

// 大号输入（文本/数字），不带上下箭头图标
export const BigInput: React.FC<{
  label: string;
  value: string | number | undefined;
  placeholder?: string;
  type?: "text" | "number";
  onChange: (v: string | number | "") => void;
  min?: number;
  max?: number;
  step?: number;
}> = ({ label, value, placeholder, type = "text", onChange, min, max, step }) => (
  <Tile>
    {/* 88px 容器内竖排，整体垂直居中；gap=0 */}
    <div className="h-full flex flex-col justify-center gap-0">
      <FloatingLabel text={label} />
      <input
        type={type}
        className="h-[28px] text-[14px] leading-[28px] bg-transparent outline-none"
        placeholder={placeholder}
        value={value ?? ""}
        min={min}
        max={max}
        step={step ?? (type === "number" ? 1 : undefined)}
        onChange={(e) => {
          const raw = e.currentTarget.value;
          if (type === "number") onChange(raw === "" ? "" : Number(raw));
          else onChange(raw);
        }}
      />
    </div>
  </Tile>
);

// 大号下拉：右侧显示上下箭头
export const BigSelect: React.FC<{
  label: string;
  value: any;
  options: { label: string; value: string | number }[];
  onChange: (v: any) => void;
}> = ({ label, value, options, onChange }) => {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  // 点击外部关闭
  React.useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (!ref.current) return;
      if (!ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const selected = options.find(o => o.value === value);

  return (
    <Tile>
      <div className="h-full flex flex-col justify-center gap-0" ref={ref}>
        <FloatingLabel text={label} />

        {/* 这一行就是“假装的 select” */}
        <div
          onClick={() => setOpen(o => !o)}
          className="
            group relative h-[28px] w-full rounded-md px-2 pr-6
            text-[14px] leading-[28px]
            cursor-pointer
            transition-colors
            hover:bg-black/5 focus-within:bg-black/10
            ring-1 ring-transparent focus-within:ring-blue-400
          "
        >
          <span className={selected ? "" : "text-black/40"}>
            {selected ? selected.label : "请选择"}
          </span>

          {/* 右侧箭头 */}
          <span className="pointer-events-none absolute right-1 top-1/2 -translate-y-1/2">
            <ArrowLineUpDown className="w-4 h-4 opacity-60 group-hover:opacity-80" />
          </span>
        </div>

        {/* 悬浮菜单 */}
        {open && (
          <SelectMenu
            options={options}
            value={value}
            onSelect={(v) => {
              onChange(v);
              setOpen(false);
            }}
          />
        )}
      </div>
    </Tile>
  );
};

// 开关项：上下结构；单项时只占左半列（col-span-1）
export const SwitchTile: React.FC<{
    label: string; // 说明文案
    checked: boolean;
    onChange: (v: boolean) => void;
}> = ({label, checked, onChange}) => (
    <Tile>
        <div className="h-full flex flex-col justify-center gap-0">
            <FloatingLabel text={label}/>
            <div className="h-[28px] flex items-center">
                <button
                    type="button"
                    aria-pressed={checked}
                    onClick={() => onChange(!checked)}
                    className={"relative w-14 h-8 rounded-full transition-colors " + (checked ? "bg-blue-600" : "bg-black/20")}
                >
          <span
              className={
                  "absolute top-1 left-1 w-6 h-6 rounded-full bg-white shadow transition-transform " +
                  (checked ? "translate-x-6" : "")
              }
          />
                </button>
            </div>
        </div>
    </Tile>
);