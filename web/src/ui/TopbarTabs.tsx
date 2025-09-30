export default function TopbarTabs({
  tabs,
  active,
  onChange,
  extra,
  prefix,
}: {
  tabs: string[];
  active: string;
  onChange: (v: string) => void;
  extra?: React.ReactNode;
  prefix?: React.ReactNode;
}) {
  return (
    <div className="h-[72px] shrink-0 bg-white/40 dark:bg-black/10 backdrop-blur px-6 flex items-center justify-between">
      <div className="flex items-center gap-3">
        {prefix ? <div className="shrink-0">{prefix}</div> : null}
        <div className="flex items-center gap-2 text-sm">
          {tabs.map((t) => {
            const is = t === active;
            return (
              <button
                key={t}
                onClick={() => onChange(t)}
                className={[
                  "px-3 py-1.5 rounded-full transition-colors",
                  is
                    ? "bg-neutral-900 text-white dark:bg-white dark:text-neutral-900"
                    : "hover:bg-black/5 dark:hover:bg-white/10",
                ].join(" ")}
              >
                {t}
              </button>
            );
          })}
        </div>
      </div>
      <div className="flex items-center gap-2">{extra}</div>
    </div>
  );
}
