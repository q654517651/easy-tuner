import React from "react";
import { Button as HButton } from "@heroui/react";
import type { ButtonProps as HButtonProps } from "@heroui/react";

export type AppButtonKind = "filled" | "outlined";
export type AppButtonSize = "sm" | "md" | "lg";
export type AppButtonColor =
  | "primary"
  | "secondary"
  | "success"
  | "warning"
  | "danger"
  | "default";

export interface AppButtonProps
  extends Omit<HButtonProps, "variant" | "size" | "color" | "startContent" | "endContent"> {
  kind?: AppButtonKind;
  size?: AppButtonSize;
  color?: AppButtonColor;
  startIcon?: React.ReactNode;
  endIcon?: React.ReactNode;
  className?: string;
}

/**
 * 统一按钮封装（基于 HeroUI Button）：
 * - kind: filled(填充)/outlined(描边)
 * - 支持 startIcon / endIcon
 * - 轻量附加样式，保持与项目定制一致
 */
export const AppButton: React.FC<AppButtonProps> = ({
  kind = "filled",
  size = "md",
  color = "primary",
  startIcon,
  endIcon,
  className,
  children,
  ...rest
}) => {
  // 映射到 HeroUI 的 variant/size
  const variant: HButtonProps["variant"] = kind === "outlined" ? "bordered" : "solid";
  const sz: HButtonProps["size"] = size;

  // 追加一些统一的交互/阴影（在不破坏主题的前提下）
  const extra =
    kind === "outlined"
      ? "hover:bg-neutral-100/60 dark:hover:bg-white/10 [border-width:1.5px]"
      : "hover:opacity-90";

  return (
    <HButton
      variant={variant}
      size={sz}
      color={color as any}
      className={["h-8", extra, className].filter(Boolean).join(" ")}
      startContent={startIcon}
      endContent={endIcon}
      {...rest}
    >
      {children}
    </HButton>
  );
};

export default AppButton;

