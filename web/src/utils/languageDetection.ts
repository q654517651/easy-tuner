/**
 * 语言检测和自动设置工具
 */

export type SupportedLanguage = "zh" | "en";

/**
 * 从浏览器语言或系统语言检测最佳匹配的应用语言
 */
export function detectSystemLanguage(): SupportedLanguage {
  // 获取浏览器语言列表（优先级从高到低）
  const browserLanguages = [
    navigator.language,
    ...(navigator.languages || [])
  ].filter(Boolean);

  // 语言映射规则
  for (const browserLang of browserLanguages) {
    const lang = browserLang.toLowerCase();

    // 中文检测（简体、繁体、各地区）
    if (lang.startsWith('zh')) {
      return 'zh';
    }

    // 英文检测（作为fallback，因为很多系统都有英文）
    if (lang.startsWith('en')) {
      return 'en';
    }
  }

  // 默认回退到中文（因为这是中文应用）
  return 'zh';
}

/**
 * 获取当前语言设置（考虑用户偏好和系统检测）
 */
export function getInitialLanguage(): SupportedLanguage {
  try {
    // 1. 优先使用用户之前保存的语言偏好
    const savedLang = localStorage.getItem("lang") as SupportedLanguage;
    if (savedLang && ['zh', 'en'].includes(savedLang)) {
      return savedLang;
    }

    // 2. 检查是否是首次启动（没有保存过语言设置）
    const isFirstTime = !localStorage.getItem("lang");
    if (isFirstTime) {
      // 首次启动时自动检测系统语言
      const detectedLang = detectSystemLanguage();
  // 静默：仅在失败时警告

      // 保存检测到的语言作为用户偏好
      localStorage.setItem("lang", detectedLang);
      return detectedLang;
    }

    // 3. 默认回退
    return 'zh';
  } catch (error) {
    console.warn('[Language] 检测语言失败，使用默认中文:', error);
    return 'zh';
  }
}

/**
 * 获取当前语言的locale字符串（用于API调用）
 */
export function getLocaleString(lang?: SupportedLanguage): string {
  const currentLang = lang || getInitialLanguage();

  switch (currentLang) {
    case 'zh':
      return 'zh-CN';
    case 'en':
      return 'en-US';
    default:
      return 'zh-CN';
  }
}

/**
 * 判断是否为中文环境（用于国内源判断）
 */
export function isChineseLocale(lang?: SupportedLanguage): boolean {
  const currentLang = lang || getInitialLanguage();
  return currentLang === 'zh';
}
