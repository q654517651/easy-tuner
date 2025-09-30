import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { getInitialLanguage, type SupportedLanguage } from "../utils/languageDetection";

type Lang = "zh" | "en";
type Dict = Record<string, string>;

type Ctx = {
  lang: Lang;
  t: (key: string, vars?: Record<string, string | number>, count?: number) => string;
  setLang: (l: Lang) => void;
};

const I18nCtx = createContext<Ctx | null>(null);

// 轻量缓存，避免重复加载
const dictCache: Partial<Record<Lang, Dict>> = { zh: {} };

async function loadDict(lang: Lang): Promise<Dict> {
  if (dictCache[lang]) return dictCache[lang]!;

  try {
    // ✅ 前端按需加载（无需后端）：Vite 支持直接导入 JSON
    const mod = await import(`./dicts/${lang}.json`);
    dictCache[lang] = (mod.default || mod) as Dict;
    return dictCache[lang]!;
  } catch (error) {
    console.warn(`Failed to load language dict for ${lang}:`, error);
    dictCache[lang] = {};
    return {};
  }
}

function format(str: string, vars?: Record<string, string | number>) {
  if (!vars) return str;
  return str.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? `{${k}}`));
}

function selectPlural(base: string, count?: number) {
  // 极简：英文常见复数规则，中文直接返回
  if (typeof count !== "number") return base;
  // 约定 key 中使用 `|` 分割：如 "文件|{count} files"
  // 若译文不含 | 则直接返回
  return base.includes("|") ? (count === 1 ? base.split("|")[0] : base.split("|")[1]) : base;
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLang] = useState<Lang>(() => {
    return getInitialLanguage() as Lang;
  });
  const [dict, setDict] = useState<Dict>({});

  useEffect(() => {
    try {
      localStorage.setItem("lang", lang);
    } catch {
      // ignore localStorage errors
    }
    if (lang === "zh") {
      setDict({});
      return;
    }
    loadDict(lang).then(setDict);
  }, [lang]);

  const t = useMemo(() => {
    return (key: string, vars?: Record<string, string | number>, count?: number) => {
      // 支持命名空间 key；找不到时回退中文原文
      let raw = dict[key] ?? key;

      // 如果是中文模式且key包含命名空间前缀，提取原始中文文本
      if (lang === "zh" && key.includes(']')) {
        const match = key.match(/\[.*?\](.+)/);
        if (match) {
          raw = match[1]; // 提取]后面的中文部分
        }
      }

      const plural = selectPlural(raw, count);
      return format(plural, vars);
    };
  }, [dict, lang]);

  const value = useMemo(() => ({ lang, t, setLang }), [lang, t]);

  return <I18nCtx.Provider value={value}>{children}</I18nCtx.Provider>;
}

export function useI18n() {
  const ctx = useContext(I18nCtx);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}