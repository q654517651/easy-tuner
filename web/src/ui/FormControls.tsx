/**
 * FormControls.tsx
 * -----------------------------------------------------------------------------
 * 表单控件组件库 - 统一的表单输入控件样式
 *
 * 包含的控件：
 * - Tile: 统一的控件外框容器
 * - FloatingLabel: 浮动标签组件
 * - BigInput: 大号文本/数字输入框
 * - BigSelect: 大号下拉选择框
 * - SwitchTile: 开关切换控件
 * - TextareaTile: 多行文本输入框
 * - FormGroup: 表单分组卡片
 *
 * 设计特点：
 * - 统一的视觉风格和交互体验
 * - 支持浮动标签设计
 * - 响应式布局适配
 * - TypeScript类型安全
 * -----------------------------------------------------------------------------
 */

import React from "react";

/* ========= 基础组件 ========= */

// 统一控件外框：高度 88，圆角 16，内文字 14
export const Tile: React.FC<React.PropsWithChildren<{ className?: string }>> = ({
  className,
  children
}) => (
  <div
    className={[
      "relative h-[88px] rounded-2xl bg-white ring-1 ring-black/10 px-4",
      className || ""
    ].join(" ")}
  >
    {children}
  </div>
);

// 标签组件（28px高度）
export const Label: React.FC<{ text: string }> = ({ text }) => (
  <div className="h-[28px] flex items-center text-[14px] text-black/40">{text}</div>
);

// 保留FloatingLabel用于向后兼容（已弃用，请使用Label）
export const FloatingLabel = Label;

/* ========= 输入控件 ========= */

// 大号输入框（文本/数字），不带上下箭头图标
export interface BigInputProps {
  label: string;
  value: string | number | undefined;
  placeholder?: string;
  type?: "text" | "number";
  onChange: (v: string | number | "") => void;
  min?: number;
  max?: number;
  step?: number;
  className?: string;
}

export const BigInput: React.FC<BigInputProps> = ({
  label,
  value,
  placeholder,
  type = "text",
  onChange,
  min,
  max,
  step,
  className
}) => (
  <Tile className={className}>
    <div className="flex flex-col justify-center h-full px-4">
      <Label text={label} />
      <input
        type={type}
        className="h-[28px] bg-transparent outline-none text-[14px] flex items-center"
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

/* ========= 选择控件 ========= */

export type SelectOption = { label: string; value: any };

// 大号下拉选择框：右侧显示上下箭头
export interface BigSelectProps {
  label: string;
  value: any;
  options: SelectOption[];
  onChange: (v: any) => void;
  className?: string;
}

export const BigSelect: React.FC<BigSelectProps> = ({
  label,
  value,
  options,
  onChange,
  className
}) => (
  <Tile className={className}>
    <div className="flex flex-col justify-center h-full px-4 relative">
      <Label text={label} />
      <select
        className="h-[28px] bg-transparent outline-none text-[14px] appearance-none pr-8"
        value={value ?? (options[0]?.value ?? "")}
        onChange={(e) => onChange(e.currentTarget.value)}
      >
        {options.map((opt) => (
          <option key={String(opt.value)} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      {/* 上下箭头（仅下拉显示） */}
      <div className="absolute right-0 top-1/2 -translate-y-1/2 grid pointer-events-none">
        <svg width="14" height="14" viewBox="0 0 24 24" className="opacity-60">
          <polyline fill="none" stroke="currentColor" strokeWidth="2" points="6 14 12 8 18 14" />
        </svg>
        <svg width="14" height="14" viewBox="0 0 24 24" className="opacity-60 -mt-1">
          <polyline fill="none" stroke="currentColor" strokeWidth="2" points="6 10 12 16 18 10" />
        </svg>
      </div>
    </div>
  </Tile>
);

/* ========= 开关控件 ========= */

// 开关项：上下结构；单项时只占左半列（col-span-1）
export interface SwitchTileProps {
  label: string; // 说明文案
  checked: boolean;
  onChange: (v: boolean) => void;
  className?: string;
}

export const SwitchTile: React.FC<SwitchTileProps> = ({
  label,
  checked,
  onChange,
  className
}) => (
  <Tile className={className}>
    <div className="flex flex-col justify-center h-full px-4">
      <Label text={label} />
      <div className="h-[28px] flex items-center">
        <button
          type="button"
          aria-pressed={checked}
          onClick={() => onChange(!checked)}
          className={[
            "relative w-14 h-8 rounded-full transition-colors",
            checked ? "bg-blue-600" : "bg-black/20"
          ].join(" ")}
        >
          <span
            className={[
              "absolute top-1 left-1 w-6 h-6 rounded-full bg-white shadow transition-transform",
              checked ? "translate-x-6" : ""
            ].join(" ")}
          />
        </button>
      </div>
    </div>
  </Tile>
);

/* ========= 多行文本控件 ========= */

// 多行文本输入框
export interface TextareaTileProps {
  label: string;
  value: string;
  placeholder?: string;
  rows?: number;
  onChange: (v: string) => void;
  className?: string;
}

export const TextareaTile: React.FC<TextareaTileProps> = ({
  label,
  value,
  placeholder,
  rows = 4,
  onChange,
  className
}) => (
  <div className={className}>
    <label className="block text-[14px] font-medium mb-2">{label}</label>
    <textarea
      className="w-full px-3 py-2 border border-gray-300 rounded-lg resize-none text-[14px]"
      rows={rows}
      value={value || ""}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
    />
  </div>
);

/* ========= 分组控件 ========= */

// 表单分区容器：用于包装FormGroup，提供滚动定位和间距
export interface FormSectionProps {
  sectionId: string;
  title: string;
  children: React.ReactNode;
  onRegisterRef?: (id: string, element: HTMLDivElement | null) => void;
  className?: string;
}

export const FormSection: React.FC<FormSectionProps> = ({
  sectionId,
  title,
  children,
  onRegisterRef,
  className
}) => (
  <div
    ref={(el) => onRegisterRef?.(sectionId, el)}
    className={className}
  >
    <FormGroup title={title} anchorId={sectionId}>
      {children}
    </FormGroup>
  </div>
);

// 分组卡片：背景、圆角、padding=24，标题 14 加粗
export interface FormGroupProps {
  title: string;
  anchorId?: string;
  children: React.ReactNode;
  className?: string;
}

export const FormGroup: React.FC<FormGroupProps> = ({
  title,
  anchorId,
  children,
  className
}) => (
  <div
    id={anchorId}
    className={[
      "rounded-2xl bg-[#F7F7F8] dark:bg-white/5 ring-1 ring-black/5 dark:ring-white/10 p-6",
      className || ""
    ].join(" ")}
  >
    <div className="text-[14px] font-semibold mb-4">{title}</div>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{children}</div>
  </div>
);

/* ========= 导出所有组件 ========= */

// 所有表单控件组件都已在上面定义和导出
// 这个文件只包含纯功能组件，具体的选项值由调用方传递