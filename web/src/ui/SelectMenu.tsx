import * as React from "react";

export interface SelectMenuOption {
  label: string;
  value: string | number;
}

export interface SelectMenuProps {
  options: SelectMenuOption[];
  value?: string | number;
  onSelect: (v: string | number) => void;
  className?: string;     // 整个浮层样式
  itemClassName?: string; // 单项样式
}

/**
 * 仅浮层菜单，不包含触发按钮
 */
export const SelectMenu: React.FC<SelectMenuProps> = ({
  options,
  value,
  onSelect,
  className = "",
  itemClassName = "",
}) => {
  return (
    <ul
      className={[
        "absolute left-0 top-full mt-1 w-full",
        "z-50 rounded-md bg-white shadow-lg ring-1 ring-black/10 max-h-60 overflow-auto",
        className,
      ].join(" ")}
    >
      {options.map(opt => (
        <li
          key={String(opt.value)}
          onClick={() => onSelect(opt.value)}
          className={[
            "h-[28px] px-2 cursor-pointer select-none text-[14px] leading-[28px]",
            value === opt.value
              ? "bg-blue-50 text-blue-700"
              : "hover:bg-black/5",
            itemClassName,
          ].join(" ")}
        >
          {opt.label}
        </li>
      ))}
    </ul>
  );
};
