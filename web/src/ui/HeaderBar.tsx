import { useNavigate, useLocation } from "react-router-dom";
import { Breadcrumbs, BreadcrumbItem, Button } from "@heroui/react";
import type { ActionDesc } from "../ui/ActionButton";
import { ActionGroup } from "../ui/ActionButton";
import ArrowLineLeftIcon from "@/assets/icon/ArrowLineLeft.svg?react";

type Crumb = {
  label: string;
  path?: string; // 有 path 表示可点击
};

// 顶部已有：import { ActionDesc, ActionGroup } from "../ui/ActionButton";  ✅:contentReference[oaicite:0]{index=0}

export default function HeaderBar({
  crumbs = [],
  actions,
}: {
  crumbs: Crumb[];
  actions?: React.ReactNode | ActionDesc[]; // ✅ 支持"动作数组"或旧的 ReactNode
}) {
  const navigate = useNavigate();
  const location = useLocation();

  // 自动检测是否为2级页面（需要显示返回按钮）
  const isDetailPage = /^\/(datasets|tasks)\/[^\/]+/.test(location.pathname);
  const showBack = isDetailPage;

  return (
    <header className="h-16 shrink-0 px-6 flex items-center justify-between border-b border-black/10 dark:border-white/10 bg-white/60 dark:bg-black/20 backdrop-blur">
      {/* 左侧：返回按钮 + 面包屑 - 固定最小高度避免闪烁 */}
      <div className="flex items-center gap-2 min-h-[40px]">
        {showBack && (
          <Button
            isIconOnly
            variant="bordered"
            size="sm"
            className="border-1"
            onPress={() => {
              // 根据当前页面类型决定返回路径，避免使用 navigate(-1)
              if (location.pathname.startsWith('/datasets/')) {
                navigate('/datasets');
              } else if (location.pathname.startsWith('/tasks/')) {
                navigate('/tasks');
              } else {
                navigate(-1); // 兜底方案
              }
            }}
            aria-label="返回"
          >
            <span className="flex items-center justify-center w-4 h-4 [&>svg]:w-4 [&>svg]:h-4 [&_path]:fill-current text-gray-900 dark:text-gray-100">
              <ArrowLineLeftIcon />
            </span>
          </Button>
        )}

        {/* 面包屑 - 使用HeroUI组件，确保文本不换行 */}
        <Breadcrumbs className="flex-shrink-0">
          {crumbs.map((c, i) => {
            const isLast = i === crumbs.length - 1;
            return (
              <BreadcrumbItem
                key={i}
                onPress={c.path && !isLast ? () => navigate(c.path!) : undefined}
                className={`whitespace-nowrap ${isLast ? "cursor-default" : "cursor-pointer"}`}
              >
                {c.label}
              </BreadcrumbItem>
            );
          })}
        </Breadcrumbs>
      </div>

      {/* 右侧：如果传的是动作数组 → 统一样式渲染；否则保留旧插槽 */}
      <div className="flex items-center gap-2 min-h-[40px]">
        {Array.isArray(actions)
          ? <ActionGroup actions={actions} />
          : actions}
      </div>
    </header>
  );
}
