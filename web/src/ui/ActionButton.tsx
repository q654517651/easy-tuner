import React from "react";
import { useNavigate, Link } from "react-router-dom";

export type ActionDesc = {
  key: string;
  label?: React.ReactNode;
  icon?: React.ReactNode;
  to?: string;                 // 跳转型
  onClick?: () => void;        // 行为型
  disabled?: boolean;
  variant?: "primary" | "outline" | "ghost" | "danger" | "success";
  size?: "sm" | "md";
  title?: string;
};

const variantCls: Record<NonNullable<ActionDesc["variant"]>, string> = {
  primary: "bg-black text-white dark:bg-white dark:text-black hover:opacity-90 border border-black/10 dark:border-white/10",
  outline: "border border-black/10 dark:border-white/15 hover:bg-black/5 dark:hover:bg-white/10",
  ghost:   "hover:bg-black/5 dark:hover:bg-white/10",
  danger:  "bg-red-500 text-white hover:bg-red-600",
  success: "bg-green-500 text-white hover:bg-green-600",
};

const sizeCls: Record<NonNullable<ActionDesc["size"]>, string> = {
  sm: "px-3 py-1.5 text-sm rounded-lg",
  md: "px-4 py-2 text-base rounded-xl",
};

export function ActionButton({
  variant = "outline",
  size = "sm",
  ...a
}: ActionDesc) {
  const cls = `${sizeCls[size]} ${variantCls[variant]} inline-flex items-center gap-2 disabled:opacity-50 disabled:pointer-events-none`;
  if (a.to) {
    return (
      <Link to={a.to} className={cls} title={a.title}>
        {a.icon}{a.label}
      </Link>
    );
  }
  return (
    <button onClick={a.onClick} disabled={a.disabled} className={cls} title={a.title}>
      {a.icon}{a.label}
    </button>
  );
}

export function ActionGroup({ actions }: { actions: ActionDesc[] }) {
  return (
    <div className="flex items-center gap-2">
      {actions.map(({ key, ...rest }) => <ActionButton key={key} {...rest} />)}
    </div>
  );
}
