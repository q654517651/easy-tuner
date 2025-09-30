import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface ThemeContextType {
  isDark: boolean;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};

interface ThemeProviderProps {
  children: ReactNode;
}

export const ThemeProvider = ({ children }: ThemeProviderProps) => {
  const [isDark, setIsDark] = useState(() => {
    // 初始化时检查当前主题状态
    return document.documentElement.classList.contains('dark');
  });

  const toggleTheme = () => {
    const newIsDark = !isDark;
    const root = document.documentElement;

    // 添加禁用过渡的类名 - 防止半透明元素不同步
    root.classList.add('theme-switching');

    setIsDark(newIsDark);

    if (newIsDark) {
      root.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      root.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }

    // 同步Electron标题栏主题
    if (window.api?.updateTitleBarTheme) {
      window.api.updateTitleBarTheme(newIsDark).catch(console.error);
    }

    // 等待2帧后移除禁用类 - 确保CSS变量完全更新
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        root.classList.remove('theme-switching');
      });
    });
  };

  // 监听系统主题变化
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = () => {
      // 只有在没有用户设置时才跟随系统主题
      const savedTheme = localStorage.getItem('theme');
      if (!savedTheme) {
        const newIsDark = mediaQuery.matches;
        setIsDark(newIsDark);
        if (newIsDark) {
          document.documentElement.classList.add('dark');
        } else {
          document.documentElement.classList.remove('dark');
        }
      }
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  return (
    <ThemeContext.Provider value={{ isDark, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};