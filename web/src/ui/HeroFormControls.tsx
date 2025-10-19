/**
 * HeroFormControls.tsx
 * -----------------------------------------------------------------------------
 * 基于 HeroUI 的表单控件组件库（统一表单控件解决方案）
 *
 * 包含的控件：
 * - HeroInput: 基于 HeroUI Input 的文本/数字输入框
 * - HeroSelect: 基于 HeroUI Select 的下拉选择框
 * - HeroSwitch: 基于 HeroUI Switch 的开关控件
 * - HeroTextarea: 基于 HeroUI Textarea 的多行文本输入框
 * - FormGroup: 表单分组卡片容器
 * - FormSection: 表单分区容器（带滚动定位）
 *
 * 设计特点：
 * - 使用 HeroUI 的中号尺寸 (size="md")
 * - 统一的背景色、边框和悬停效果
 * - 完整的类型安全和 TypeScript 支持
 * - 支持深色模式自适应
 * -----------------------------------------------------------------------------
 */

import React from "react";
import { Input, Select, SelectItem, Switch, Textarea } from "@heroui/react";

/* ========= 类型定义 ========= */

export type SelectOption = { label: string; value: any };

/* ========= HeroUI 输入控件 ========= */

// HeroUI 文本/数字输入框
export interface HeroInputProps {
  label: string;
  value: string | number | undefined;
  placeholder?: string;
  type?: "text" | "number" | "email" | "password";
  onChange: (v: string | number | "") => void;
  min?: number;
  max?: number;
  step?: number;
  className?: string;
  isRequired?: boolean;
  isInvalid?: boolean;
  isDisabled?: boolean;
  errorMessage?: string;
  labelPlacement?: "inside" | "outside-top";
}

// export const HeroInput: React.FC<HeroInputProps> = ({
//   label,
//   value,
//   placeholder,
//   type = "text",
//   onChange,
//   min,
//   max,
//   step,
//   className,
//   isRequired = false,
//   isInvalid = false,
//   errorMessage
// }) => (
//   <Input
//     size="lg"
//     type={type}
//     label={label}
//     placeholder={placeholder || label}
//     value={String(value ?? "")}
//     min={min}
//     max={max}
//     step={step}
//     isRequired={isRequired}
//     isInvalid={isInvalid}
//     errorMessage={errorMessage}
//     className={className}
//     onChange={(e) => {
//       const raw = e.target.value;
//       if (type === "number") {
//         onChange(raw === "" ? "" : Number(raw));
//       } else {
//         onChange(raw);
//       }
//     }}
//   />
// );

export const HeroInput: React.FC<HeroInputProps> = ({
  label,
  value,
  placeholder,
  type = "text",
  onChange,
  min,
  max,
  step,
  className,
  isRequired = false,
  isInvalid = false,
  isDisabled = false,
  errorMessage,
  labelPlacement = "inside",
}) => (
  <Input
    size="md"
    type={type}
    label={label}
    labelPlacement={labelPlacement === "outside-top" ? "outside" : labelPlacement}
    placeholder={placeholder || (typeof label === "string" ? label : undefined)}
    value={String(value ?? "")}
    min={min}
    max={max}
    step={step}
    isRequired={isRequired}
    isInvalid={isInvalid}
    isDisabled={isDisabled}
    errorMessage={errorMessage}
    className={className}
    classNames={
      labelPlacement === "inside"
        ? {
            inputWrapper:"shadow-none bg-white dark:bg-[#2A2A2A] [border-width:1.5px] border-black/10 dark:border-white/5 px-4 !py-3 h-auto " +
                "hover:bg-black/4 dark:hover:bg-white/4 data-[hover=true]:bg-black/4 dark:data-[hover=true]:bg-white/4",
            label:"h-6 h-auto !text-default-400",
            innerWrapper:"h-6 mt-6",
          }
        : {
            mainWrapper: "pt-6",
            inputWrapper:"shadow-none bg-white dark:bg-[#2A2A2A] [border-width:1.5px] border-black/10 dark:border-white/5 px-4 py-2.5 h-auto " +
                "hover:bg-black/4 dark:hover:bg-white/4 data-[hover=true]:bg-black/4 dark:data-[hover=true]:bg-white/4",
            label:"!text-default-400 text-sm",
          }
    }
    onChange={(e) => {
      const raw = e.target.value;
      if (type === "number") onChange?.(raw === "" ? "" : Number(raw));
      else onChange?.(raw);
    }}
  />
);





/* ========= HeroUI 选择控件 ========= */

// HeroUI 下拉选择框
export interface HeroSelectProps {
  label: string;
  value: any;
  options: SelectOption[];
  onChange: (v: any) => void;
  placeholder?: string;
  className?: string;
  isRequired?: boolean;
  isInvalid?: boolean;
  errorMessage?: string;
  disabledKeys?: string[];
  description?: string;
  labelPlacement?: "inside" | "outside-top";
}

export const HeroSelect: React.FC<HeroSelectProps> = ({
  label,
  value,
  options,
  onChange,
  placeholder,
  className,
  isRequired = false,
  isInvalid = false,
  errorMessage,
  disabledKeys = [],
  description,
  labelPlacement = "inside",
}) => (
  <Select
    size="md"
    label={label}
    labelPlacement={labelPlacement === "outside-top" ? "outside" : labelPlacement}
    placeholder={placeholder || label}
    selectedKeys={value ? [String(value)] : []}
    disabledKeys={disabledKeys}
    isRequired={isRequired}
    isInvalid={isInvalid}
    errorMessage={errorMessage}
    description={description}
    className={className}
    classNames={
      labelPlacement === "inside"
        ? {
            trigger:"shadow-none bg-white dark:bg-[#2A2A2A] [border-width:1.5px] border-black/10 dark:border-white/5 px-4 !py-3 h-auto " +
                "hover:bg-black/4 dark:hover:bg-white/4 data-[hover=true]:bg-black/4 dark:data-[hover=true]:bg-white/4",
            label:"h-6 h-auto !text-default-400",
            innerWrapper:"h-6 mt-6 !pt-0",
          }
        : {
            mainWrapper: "pt-6",
            trigger:"shadow-none bg-white dark:bg-[#2A2A2A] [border-width:1.5px] border-black/10 dark:border-white/5 px-4 py-2.5 h-auto " +
                "hover:bg-black/4 dark:hover:bg-white/4 data-[hover=true]:bg-black/4 dark:data-[hover=true]:bg-white/4",
            label:"!text-default-400 text-sm",
          }
    }
    onSelectionChange={(keys) => {
      const selectedKey = Array.from(keys)[0];
      if (selectedKey) {
        // 找到对应的原始值
        const selectedOption = options.find(opt => String(opt.value) === selectedKey);
        onChange(selectedOption?.value ?? selectedKey);
      }
    }}
  >
    {options.map((option) => (
      <SelectItem key={String(option.value)}>
        {option.label}
      </SelectItem>
    ))}
  </Select>
);

/* ========= HeroUI 开关控件 ========= */

// HeroUI 开关控件
export interface HeroSwitchProps {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  className?: string;
  description?: string;
}

export const HeroSwitch: React.FC<HeroSwitchProps> = ({
  label,
  checked,
  onChange,
  className,
  description: _description
}) => (
  <div
    className={`bg-white dark:bg-[#2A2A2A] [border-width:1.5px] border-black/10 dark:border-white/5 px-4 rounded-xl hover:bg-black/4 dark:hover:bg-white/4 transition-colors ${className || ''}`}
  >
    <div className="flex flex-col gap-2 py-3">
      <label className="text-xs text-default-400">{label}</label>
      <Switch
        size="sm"
        isSelected={checked}
        onValueChange={onChange}
      />
    </div>
  </div>
);

/* ========= HeroUI 多行文本控件 ========= */

// HeroUI 多行文本输入框
export interface HeroTextareaProps {
  label: string;
  value: string;
  placeholder?: string;
  rows?: number;
  onChange: (v: string) => void;
  className?: string;
  isRequired?: boolean;
  isInvalid?: boolean;
  errorMessage?: string;
}

export const HeroTextarea: React.FC<HeroTextareaProps> = ({
  label,
  value,
  placeholder,
  rows = 4,
  onChange,
  className,
  isRequired = false,
  isInvalid = false,
  errorMessage
}) => (
  <Textarea
    size="md"
    label={label}
    placeholder={placeholder || label}
    value={value || ""}
    minRows={rows}
    isRequired={isRequired}
    isInvalid={isInvalid}
    errorMessage={errorMessage}
    className={className}
    classNames={{
      inputWrapper: "shadow-none bg-white dark:bg-[#2A2A2A] [border-width:1.5px] border-black/10 dark:border-white/5 px-4 py-2.5 " +
          "hover:bg-black/4 dark:hover:bg-white/4 data-[hover=true]:bg-black/4 dark:data-[hover=true]:bg-white/4",
      label: "!text-default-400"
    }}
    onChange={(e) => onChange(e.target.value)}
  />
);

/* ========= 分组容器组件 ========= */

// 表单分组卡片：背景、圆角、padding=24，标题 14 加粗
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

/* ========= 工具函数 ========= */

// 将原有的 SelectOption 转换为 HeroUI 格式的辅助函数
export const convertToHeroOptions = (options: string[]): SelectOption[] => {
  return options.map(opt => ({ label: opt, value: opt }));
};

// 常用分辨率选项（HeroUI 版本）
export const HERO_RESOLUTION_OPTIONS: SelectOption[] = [
  { label: "1024x1024", value: "1024,1024" },
  { label: "1280x1280", value: "1280,1280" },
  { label: "1536x1536", value: "1536,1536" },
  { label: "512x512", value: "512,512" },
  { label: "768x768", value: "768,768" },
];