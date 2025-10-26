import { NavLink } from "react-router-dom";
import { Dropdown, DropdownTrigger, DropdownMenu, DropdownItem, Button } from "@heroui/react";
import { useTheme } from "../contexts/ThemeContext";
import { useI18n } from "../i18n/I18nProvider";
import { useIsElectron } from "../utils/platform";
// import sidebar_icon_home from "@/assets/icon/sidebar_icon_home.svg?react";
import DatasetIcon from "@/assets/icon/sidebar_icon_dataset.svg?react";
import CreateIcon  from "@/assets/icon/sidebar_icon_create.svg?react";
import TaskIcon    from "@/assets/icon/sidebar_icon_task.svg?react";
import SettingIcon from "@/assets/icon/sidebar_icon_setting.svg?react";
import IconLight from "@/assets/icon/icon_light.svg?react";
import IconDark from "@/assets/icon/icon_dark.svg?react";
import IconGithub from "@/assets/icon/icon_github.svg?react";
import IconInternational from "@/assets/icon/icon_International.svg?react";
import Logo from "@/assets/logo/logo.svg?react";

const Item = ({ to, label, icon }: { to: string; label: string; icon: React.ReactNode }) => (
  <NavLink
    to={to}
    className={({ isActive }) =>
      [
        "flex items-center gap-2 p-3 rounded-[16px] mx-3 my-1 text-sm transition-colors",
        isActive
          ? "bg-black/5 dark:bg-white/10"
          : "hover:bg-black/5 dark:hover:bg-white/5",
      ].join(" ")
    }
  >
    <span
        className={[
        "flex items-center justify-center w-6 h-6",
        "text-gray-900 dark:text-gray-100",
        "[&>svg]:w-5 [&>svg]:h-5",
        "[&_*]:fill-current",
        "[&_*]:stroke-none",
    ].join(" ")}
    >
        {icon}
    </span>

      <span>{label}</span>
  </NavLink>
);

const FunctionItem = ({ label, icon, onClick, dropdown }: {
  label: string;
  icon: React.ReactNode;
  onClick?: () => void;
  dropdown?: React.ReactNode;
}) => {
  if (dropdown) {
    return dropdown;
  }

  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 p-3 rounded-[16px] mx-3 my-1 text-sm transition-colors hover:bg-black/5 dark:hover:bg-white/5 w-[calc(100%-24px)]"
    >
      <span
        className={[
          "flex items-center justify-center w-6 h-6",
          "text-gray-900 dark:text-gray-100",
          "[&>svg]:w-5 [&>svg]:h-5",
          "[&_*]:fill-current",
          "[&_*]:stroke-none",
        ].join(" ")}
      >
        {icon}
      </span>
      <span>{label}</span>
    </button>
  );
};

export default function Sidebar() {
    const { isDark, toggleTheme } = useTheme();
    const { lang, setLang, t } = useI18n();
    const isElectron = useIsElectron();

    const languages = [
        { key: "zh", label: "中文", flag: "🇨🇳" },
        { key: "en", label: "English", flag: "🇺🇸" },
    ];

    const currentLanguage = languages.find(l => l.key === lang) || languages[0];

    return (
        <div className="h-full flex flex-col">
            <div className={`px-6 pb-3 flex items-center gap-2 ${isElectron ? '' : 'pt-4'}`}>
                <div className="w-8 h-8 flex items-center justify-center">
                    <Logo className="w-8 h-8" />
                </div>
        <div className="font-semibold tracking-wide">EasyTuner</div>
      </div>

        <nav className="mt-2">
            <Item to="/datasets" label={t("[nav]数据集")} icon={<DatasetIcon />}/>
            <Item to="/train/create" label={t("[nav]创建任务")} icon={<CreateIcon />}/>
            <Item to="/tasks" label={t("[nav]任务列表")} icon={<TaskIcon />}/>
            <Item to="/settings" label={t("[nav]设置")} icon={<SettingIcon />}/>
        </nav>

        {/* 功能按钮区域 */}
        <div className="mt-auto border-t border-gray-200 dark:border-gray-700 py-2">
          {/* 语言选择 */}
          <FunctionItem
            label="语言"
            icon={<IconInternational />}
            dropdown={
              <Dropdown>
                <DropdownTrigger>
                  <button className="flex items-center gap-2 p-3 rounded-[16px] mx-3 my-1 text-sm transition-colors hover:bg-black/5 dark:hover:bg-white/5 w-[calc(100%-24px)]">
                    <span className="flex items-center justify-center w-6 h-6 text-gray-900 dark:text-gray-100 [&>svg]:w-5 [&>svg]:h-5 [&_*]:fill-current [&_*]:stroke-none">
                      <IconInternational />
                    </span>
                    <span>语言</span>
                  </button>
                </DropdownTrigger>
                <DropdownMenu
                  aria-label="Language selection"
                  selectedKeys={[lang]}
                  onAction={(key) => setLang(key as any)}
                >
                  {languages.map((language) => (
                    <DropdownItem
                      key={language.key}
                      startContent={<span>{language.flag}</span>}
                    >
                      {language.label}
                    </DropdownItem>
                  ))}
                </DropdownMenu>
              </Dropdown>
            }
          />

          {/* 主题切换 */}
          <FunctionItem
            label={isDark ? "浅色模式" : "深色模式"}
            icon={isDark ? <IconLight /> : <IconDark />}
            onClick={toggleTheme}
          />

          {/* GitHub */}
          <button
            onClick={() => window.electron?.openExternal('https://github.com/q654517651/easy-tuner')}
            className="flex items-center gap-2 p-3 rounded-[16px] mx-3 my-1 text-sm transition-colors hover:bg-black/5 dark:hover:bg-white/5 w-[calc(100%-24px)] text-gray-900 dark:text-gray-100"
          >
            <span className="flex items-center justify-center w-6 h-6 [&>svg]:w-5 [&>svg]:h-5 [&_svg]:fill-current [&_path]:fill-current">
              <IconGithub />
            </span>
            <span>GitHub</span>
          </button>
        </div>

    </div>
  );
}