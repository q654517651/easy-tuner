import { Select, SelectItem } from "@heroui/react";
import { useI18n } from "../i18n/I18nProvider";

const languages = [
  { key: "zh", label: "中文", flag: "🇨🇳" },
  { key: "en", label: "English", flag: "🇺🇸" },
];

export default function LanguageSelector() {
  const { lang, setLang, t } = useI18n();

  return (
    <Select
      size="sm"
      selectedKeys={[lang]}
      onSelectionChange={(keys) => setLang(Array.from(keys)[0] as any)}
      className="w-36"
      aria-label={t("[header]语言")}
      startContent={
        <span className="text-sm">
          {languages.find(l => l.key === lang)?.flag}
        </span>
      }
    >
      {languages.map((language) => (
        <SelectItem
          key={language.key}
          textValue={language.label}
          startContent={<span>{language.flag}</span>}
        >
          {language.label}
        </SelectItem>
      ))}
    </Select>
  );
}