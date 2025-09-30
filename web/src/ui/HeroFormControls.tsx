/**
 * HeroFormControls.tsx
 * -----------------------------------------------------------------------------
 * 基于 HeroUI 的表单控件组件库
 *
 * 包含的控件：
 * - HeroInput: 基于 HeroUI Input 的文本/数字输入框
 * - HeroSelect: 基于 HeroUI Select 的下拉选择框
 * - HeroSwitch: 基于 HeroUI Switch 的开关控件
 * - HeroTextarea: 基于 HeroUI Textarea 的多行文本输入框
 * - FormSection: 表单分区容器（复用原有组件）
 *
 * 设计特点：
 * - 使用 HeroUI 的大号尺寸 (size="lg")
 * - 标签作为 placeholder 显示
 * - 统一的接口设计，便于替换原有控件
 * - 保持与原有 FormControls 相同的 props 接口
 * -----------------------------------------------------------------------------
 */

import React from "react";
import { Input, Select, SelectItem, Switch, Textarea } from "@heroui/react";
import { FormSection } from "./FormControls"; // 复用原有的 FormSection

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
  errorMessage?: string;
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
  errorMessage,
}) => (
  <Input
    size="md"
    type={type}
    // inside 是默认，不改
    label={label}
    placeholder={placeholder || (typeof label === "string" ? label : undefined)}
    value={String(value ?? "")}
    min={min}
    max={max}
    step={step}
    isRequired={isRequired}
    isInvalid={isInvalid}
    errorMessage={errorMessage}
    className={className}
    // classNames={{
    //   inputWrapper:"shadow-none bg-white dark:bg-[#2A2A2A] border border-black/10 dark:border-white/5 px-5 !py-4 " +
    //       "h-auto !hover:bg-transparent data-[hover=true]:!bg-transparent focus-within:!bg-transparent",
    //   label:"h-7 h-auto !text-default-400",
    //   innerWrapper:"h-7 mt-7",
    // }}
    classNames={{
      inputWrapper:"shadow-none bg-white dark:bg-[#2A2A2A] border border-black/10 dark:border-white/5 px-4 !py-3 " +
          "h-auto !hover:bg-transparent data-[hover=true]:!bg-transparent focus-within:!bg-transparent",
      label:"h-6 h-auto !text-default-400",
      innerWrapper:"h-6 mt-6",
    }}
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
  description
}) => (
  <Select
    size="lg"
    label={label}
    placeholder={placeholder || label}
    selectedKeys={value ? [String(value)] : []}
    disabledKeys={disabledKeys}
    isRequired={isRequired}
    isInvalid={isInvalid}
    errorMessage={errorMessage}
    description={description}
    className={className}
      classNames={{
      trigger:"shadow-none bg-white dark:bg-[#2A2A2A] border border-black/10 dark:border-white/5 px-4 !py-3 " +
          "h-auto !hover:bg-transparent data-[hover=true]:!bg-transparent focus-within:!bg-transparent",
      label:"h-6 h-auto !text-default-400",
      innerWrapper:"h-6 mt-6 !pt-0",
    }}
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
      <SelectItem key={String(option.value)} value={option.value}>
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
  description
}) => (
  <div className={className}>
    <Switch
      size="lg"
      isSelected={checked}
      onValueChange={onChange}
    >
      <div className="flex flex-col">
        <span className="text-medium">{label}</span>
        {description && (
          <span className="text-small text-default-400">{description}</span>
        )}
      </div>
    </Switch>
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
    size="lg"
    label={label}
    placeholder={placeholder || label}
    value={value || ""}
    minRows={rows}
    isRequired={isRequired}
    isInvalid={isInvalid}
    errorMessage={errorMessage}
    className={className}
    onChange={(e) => onChange(e.target.value)}
  />
);

/* ========= 导出复用组件 ========= */

// 导出 FormSection 以保持一致性
export { FormSection };

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