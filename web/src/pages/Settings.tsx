import React, { useState, useEffect, useCallback } from "react";
import { Tabs, Tab, addToast, Button } from "@heroui/react";
import HeaderBar from "../ui/HeaderBar";
import GroupCard from "../ui/GroupCard";
import { HeroInput, HeroSelect, HeroSwitch, HeroTextarea, type SelectOption } from "../ui/HeroFormControls";
import { getLocaleString } from "../utils/languageDetection";

// 新增类型定义
interface ModelPathField {
  key: string;
  label: string;
  help: string;
  setting_path: string;
}

interface ModelPathGroup {
  title: string;
  fields: ModelPathField[];
}

interface ModelPathsSchema {
  [modelType: string]: ModelPathGroup;
}

// ============================
// 类型定义
// ============================

interface MusubiConfig {
  git_repository: string;
  git_branch: string;
  installation_path: string;
  status: "installed" | "not_found" | "error" | "updating";
  version: string;
  last_check: string;
  commit_hash?: string;
  commit_date?: string;
  branch?: string;
  message?: string;
}

interface MusubiRelease {
  tag: string;
  version: string;
  commit_hash: string;
  date: string;
  message: string;
  description: string;
}

interface ModelPaths {
  qwen_image: {
    dit_path: string;
    vae_path: string;
    text_encoder_path: string;
  };
  flux: {
    dit_path: string;
    vae_path: string;
    text_encoder_path: string;
    clip_path: string;
  };
  stable_diffusion: {
    unet_path: string;
    vae_path: string;
    text_encoder_path: string;
    clip_path: string;
  };
}

interface APIModelConfig {
  enabled: boolean;
  api_key: string;
  base_url: string;
  model_name: string;
  supports_video: boolean;
  max_tokens: number;
  temperature: number;
}

interface LabelingConfig {
  default_prompt: string;
  translation_prompt: string;
  selected_model: string;
  delay_between_calls: number;
  models: {
    gpt: APIModelConfig;
    claude: APIModelConfig;
    lm_studio: APIModelConfig;
    local_qwen_vl: APIModelConfig;
  };
}

interface AppSettings {
  musubi: MusubiConfig;
  model_paths: ModelPaths;
  labeling: LabelingConfig;
}

// ============================
// UI 组件
// ============================

function StatusBadge({ status }: { status: string }) {
  const getStatusConfig = (status: string) => {
    switch (status) {
      case "installed":
        return { color: "bg-green-100 text-green-800", text: "已安装" };
      case "not_found":
        return { color: "bg-red-100 text-red-800", text: "未安装" };
      case "error":
        return { color: "bg-red-100 text-red-800", text: "错误" };
      case "updating":
        return { color: "bg-blue-100 text-blue-800", text: "更新中" };
      default:
        return { color: "bg-gray-100 text-gray-800", text: "未知" };
    }
  };

  const config = getStatusConfig(status);
  return (
    <span className={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${config.color}`}>
      {config.text}
    </span>
  );
}

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center py-8">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
    </div>
  );
}

// ============================
// 主组件
// ============================

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<"后端状态" | "模型路径" | "打标设置">("后端状态");
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [releases, setReleases] = useState<MusubiRelease[]>([]);
  const [releasesLoading, setReleasesLoading] = useState(false);
  const [modelPathsSchema, setModelPathsSchema] = useState<ModelPathsSchema | null>(null);
  const [fixingEnvironment, setFixingEnvironment] = useState(false);
  const [fixingTrainer, setFixingTrainer] = useState(false);

  // 防抖保存函数
  const debouncedSave = useCallback(
    debounce(async (settings: AppSettings) => {
      try {
        setSaving(true);

        const response = await fetch("/api/v1/settings", {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(settings),
        });

        const result = await response.json();
        if (result.success) {
          // 静默保存，不显示提示
        } else {
          throw new Error(result.message || "保存失败");
        }
      } catch (err) {
        addToast({
          title: "保存失败",
          description: err instanceof Error ? err.message : "保存失败",
          color: "danger",
          timeout: 3000
        });
      } finally {
        setSaving(false);
      }
    }, 1000),
    []
  );

  // 加载设置
  const loadSettings = async () => {
    try {
      setLoading(true);

      const response = await fetch("/api/v1/settings");
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const result = await response.json();
      if (result.success) {
        setSettings(result.data);
      } else {
        throw new Error(result.message || "加载设置失败");
      }
    } catch (err) {
      addToast({
        title: "加载失败",
        description: err instanceof Error ? err.message : "网络错误",
        color: "danger",
        timeout: 3000
      });
    } finally {
      setLoading(false);
    }
  };

  // 切换到指定版本
  const switchToVersion = async (release: MusubiRelease) => {
    try {
      const response = await fetch("/api/v1/settings/musubi/switch-version", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          version: release.version,
          commit_hash: release.commit_hash,
        }),
      });

      const result = await response.json();
      if (result.success) {
        addToast({
          title: "切换成功",
          description: `已切换到版本 ${release.version}`,
          color: "success",
          timeout: 3000
        });

        // 重新加载设置以更新状态
        loadSettings();
      } else {
        throw new Error(result.message || "切换版本失败");
      }
    } catch (err) {
      addToast({
        title: "切换失败",
        description: err instanceof Error ? err.message : "切换版本失败",
        color: "danger",
        timeout: 3000
      });
    }
  };

  // 加载Musubi发布历史
  const loadMusubiReleases = async (forceRefresh: boolean = false) => {
    try {
      setReleasesLoading(true);
      const response = await fetch(`/api/v1/settings/musubi/releases?limit=10&force_refresh=${forceRefresh}`);
      const result = await response.json();

      if (result.success) {
        setReleases(result.data || []);
        if (forceRefresh) {
          addToast({
            title: "刷新成功",
            description: "发布历史已刷新",
            color: "success",
            timeout: 3000
          });
        }
      }
    } catch (err) {
      console.error("加载发布历史失败:", err);
      addToast({
        title: "加载失败",
        description: "加载发布历史失败",
        color: "danger",
        timeout: 3000
      });
    } finally {
      setReleasesLoading(false);
    }
  };

  // 修复训练环境
  const fixEnvironment = async () => {
    try {
      setFixingEnvironment(true);
      addToast({
        title: "开始修复",
        description: "正在修复训练环境，这可能需要几分钟时间...",
        color: "primary",
        timeout: 3000
      });

      // 获取当前应用语言对应的locale
      const locale = getLocaleString();

      const response = await fetch("/api/v1/settings/musubi/fix-environment", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          locale: locale
        }),
      });

      const result = await response.json();
      if (result.success) {
        addToast({
          title: "修复成功",
          description: result.message || "训练环境修复成功",
          color: "success",
          timeout: 5000
        });
        // 重新加载设置以更新状态
        loadSettings();
      } else {
        throw new Error(result.message || "修复失败");
      }
    } catch (err) {
      addToast({
        title: "修复失败",
        description: err instanceof Error ? err.message : "训练环境修复失败",
        color: "danger",
        timeout: 5000
      });
    } finally {
      setFixingEnvironment(false);
    }
  };

  // 修复训练器安装
  const fixTrainerInstallation = async () => {
    try {
      setFixingTrainer(true);
      addToast({
        title: "开始修复",
        description: "正在更新训练器到最新版本...",
        color: "primary",
        timeout: 3000
      });

      const response = await fetch("/api/v1/settings/musubi/fix-installation", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      });

      const result = await response.json();
      if (result.success) {
        addToast({
          title: "修复成功",
          description: result.message || "训练器更新成功",
          color: "success",
          timeout: 5000
        });
        // 重新加载设置和发布历史
        loadSettings();
        loadMusubiReleases(true);
      } else {
        throw new Error(result.message || "修复失败");
      }
    } catch (err) {
      addToast({
        title: "修复失败",
        description: err instanceof Error ? err.message : "训练器更新失败",
        color: "danger",
        timeout: 5000
      });
    } finally {
      setFixingTrainer(false);
    }
  };


  // 工具函数：获取嵌套值
  const getNestedValue = (obj: any, path: string): string => {
    return path.split('.').reduce((o, k) => o?.[k], obj) || "";
  };

  // 工具函数：设置嵌套值
  const setNestedValue = (obj: any, path: string, value: string) => {
    const keys = path.split('.');
    const newObj = { ...obj };
    let current = newObj;

    for (let i = 0; i < keys.length - 1; i++) {
      if (!current[keys[i]]) current[keys[i]] = {};
      current = current[keys[i]];
    }
    current[keys[keys.length - 1]] = value;

    return newObj;
  };

  // 更新嵌套配置并自动保存
  const updateNestedValue = useCallback((path: string, value: string) => {
    if (!settings) return;
    const updatedSettings = setNestedValue(settings, path, value);
    setSettings(updatedSettings);
    debouncedSave(updatedSettings);
  }, [settings, debouncedSave]);

  // 更新设置并自动保存
  const updateSettings = useCallback(
    (updatedSettings: AppSettings) => {
      setSettings(updatedSettings);
      debouncedSave(updatedSettings);
    },
    [debouncedSave]
  );

  // 加载模型路径Schema
  const loadModelPathsSchema = async () => {
    try {
      const response = await fetch("/api/v1/settings/model-paths/schema");
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const result = await response.json();
      if (result.success) {
        setModelPathsSchema(result.data);
      } else {
        throw new Error(result.message || "加载Schema失败");
      }
    } catch (err) {
      console.error("加载模型路径Schema失败:", err);
      addToast({
        title: "加载失败",
        description: err instanceof Error ? err.message : "加载Schema失败",
        color: "danger",
        timeout: 3000
      });
    }
  };

  useEffect(() => {
    loadSettings();
    loadModelPathsSchema();
    // 初始加载时也获取发布历史
    loadMusubiReleases();
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col h-full">
        <HeaderBar crumbs={[{ label: "设置" }]} />
        <LoadingSpinner />
      </div>
    );
  }


  if (!settings) return null;

  return (
    <div className="flex flex-col h-full">
      <HeaderBar crumbs={[{ label: "设置" }]} />

      <div className="h-[72px] shrink-0 bg-white/40 dark:bg-black/10 backdrop-blur px-4 flex items-center justify-between">
        <Tabs
          selectedKey={activeTab}
          onSelectionChange={(key) => setActiveTab(key as any)}
          variant="solid"
        >
          <Tab key="后端状态" title="后端状态" />
          <Tab key="模型路径" title="模型路径" />
          <Tab key="打标设置" title="打标设置" />
        </Tabs>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="px-5 pb-5 space-y-6">
        {/* 保存指示器 - 静默显示 */}
        {saving && (
          <div className="fixed bottom-4 right-4 rounded-xl bg-blue-50 border border-blue-200 p-3 shadow-lg z-50">
            <div className="text-blue-800 flex items-center gap-2 text-sm">
              <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-blue-600"></div>
              保存中...
            </div>
          </div>
        )}


        {/* 后端状态 */}
        {activeTab === "后端状态" && (
          <div className="h-full flex flex-col space-y-6">
            <GroupCard
              title="Musubi 训练器配置"
              headerContent={
                <div className="flex gap-2">
                  <Button
                    color="warning"
                    variant="light"
                    size="sm"
                    onPress={fixEnvironment}
                    isLoading={fixingEnvironment}
                    disabled={fixingEnvironment || fixingTrainer}
                  >
                    {fixingEnvironment ? "修复环境中..." : "修复环境"}
                  </Button>
                  <Button
                    color="primary"
                    variant="light"
                    size="sm"
                    onPress={fixTrainerInstallation}
                    isLoading={fixingTrainer}
                    disabled={fixingEnvironment || fixingTrainer}
                  >
                    {fixingTrainer ? "更新训练器中..." : "更新训练器"}
                  </Button>
                </div>
              }
            >
              <HeroInput
                label="Git 仓库地址"
                value={settings.musubi.git_repository}
                disabled
                onChange={(value) =>
                  updateSettings({
                    ...settings,
                    musubi: { ...settings.musubi, git_repository: String(value) },
                  })
                }
              />
              <HeroInput
                label="分支"
                value={settings.musubi.git_branch}
                onChange={(value) =>
                  updateSettings({
                    ...settings,
                    musubi: { ...settings.musubi, git_branch: String(value) },
                  })
                }
              />
              <div className="md:col-span-2">
                <HeroInput
                  label="安装位置"
                  value={settings.musubi.installation_path}
                  disabled
                  onChange={(value) =>
                    updateSettings({
                      ...settings,
                      musubi: { ...settings.musubi, installation_path: String(value) },
                    })
                  }
                />
              </div>
            </GroupCard>

            <div className="flex-1 min-h-0">
              <GroupCard
                title="发布历史"
                headerContent={
                  <button
                    onClick={() => loadMusubiReleases(true)}
                    disabled={releasesLoading}
                    className="px-4 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {releasesLoading ? "检查中..." : "检查更新"}
                  </button>
                }
              >
                <div className="md:col-span-2 h-full flex flex-col min-h-0">
                  {releasesLoading ? (
                    <div className="flex items-center justify-center py-4">
                      <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
                      <span className="ml-2 text-sm text-gray-600 dark:text-gray-300">加载中...</span>
                    </div>
                  ) : releases.length === 0 ? (
                    <div className="text-center py-8 text-gray-500">
                      <p>暂无发布历史</p>
                      <p className="text-xs mt-1">点击"检查更新"按钮获取最新信息</p>
                    </div>
                  ) : (
                    <div className="flex-1 overflow-y-auto space-y-3">
                      {releases.map((release, index) => (
                        <div
                          key={index}
                          className="border border-gray-200 dark:border-gray-600 rounded-lg p-3 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                        >
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <span className="inline-flex px-2 py-1 rounded-md bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 text-xs font-medium">
                                {release.version}
                              </span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-gray-500 dark:text-gray-400">
                                {new Date(release.date).toLocaleDateString()}
                              </span>
                              <button
                                onClick={() => switchToVersion(release)}
                                className="px-3 py-1 text-xs bg-green-100 text-green-700 hover:bg-green-200 dark:bg-green-900 dark:text-green-300 dark:hover:bg-green-800 rounded-md transition-colors"
                              >
                                切换
                              </button>
                            </div>
                          </div>
                          <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
                            {release.description || release.message || "无更新说明"}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </GroupCard>
            </div>
          </div>
        )}

        {/* 模型路径 - 动态生成 */}
        {activeTab === "模型路径" && (
          <>
            {!modelPathsSchema ? (
              <div className="flex items-center justify-center py-8">
                <div className="text-gray-600">加载模型路径配置中...</div>
              </div>
            ) : (
              Object.entries(modelPathsSchema).map(([modelType, modelGroup]) => (
                <GroupCard key={modelType} title={modelGroup.title}>
                  {modelGroup.fields.map((field) => (
                    <div key={field.key} className={field.key === 'text_encoder_path' || field.key === 'text_encoder1_path' || field.key === 'text_encoder2_path' ? "md:col-span-2" : ""}>
                      <HeroInput
                        label={field.label}
                        value={getNestedValue(settings, field.setting_path)}
                        onChange={(value) => updateNestedValue(field.setting_path, String(value))}
                        placeholder={field.help || `请输入${field.label}`}
                      />
                    </div>
                  ))}
                </GroupCard>
              ))
            )}

          </>
        )}

        {/* 打标设置 */}
        {activeTab === "打标设置" && (
          <>
            <GroupCard title="基本设置">
              <HeroSelect
                label="选择打标模型"
                value={settings.labeling.selected_model}
                options={[
                  { label: "LM Studio", value: "lm_studio" },
                  { label: "OpenAI GPT", value: "gpt" },
                  { label: "本地 Qwen-VL", value: "local_qwen_vl" },
                ]}
                onChange={(value) =>
                  updateSettings({
                    ...settings,
                    labeling: { ...settings.labeling, selected_model: value },
                  })
                }
              />
              <HeroInput
                label="调用延迟 (秒)"
                type="number"
                min={0}
                step={0.1}
                value={settings.labeling.delay_between_calls}
                onChange={(value) =>
                  updateSettings({
                    ...settings,
                    labeling: {
                      ...settings.labeling,
                      delay_between_calls: Number(value) || 0,
                    },
                  })
                }
              />
              <div className="md:col-span-2">
                <HeroTextarea
                  label="默认打标提示词"
                  value={settings.labeling.default_prompt}
                  rows={4}
                  onChange={(value) =>
                    updateSettings({
                      ...settings,
                      labeling: { ...settings.labeling, default_prompt: String(value) },
                    })
                  }
                />
              </div>
              <div className="md:col-span-2">
                <HeroTextarea
                  label="翻译提示词"
                  value={settings.labeling.translation_prompt}
                  rows={4}
                  onChange={(value) =>
                    updateSettings({
                      ...settings,
                      labeling: { ...settings.labeling, translation_prompt: String(value) },
                    })
                  }
                />
              </div>
            </GroupCard>

            {settings.labeling.selected_model === "gpt" && (
            <GroupCard title="OpenAI GPT 配置">
              <HeroInput
                label="API Key"
                value={settings.labeling.models.gpt.api_key}
                placeholder="sk-..."
                onChange={(value) =>
                  updateSettings({
                    ...settings,
                    labeling: {
                      ...settings.labeling,
                      models: {
                        ...settings.labeling.models,
                        gpt: {
                          ...settings.labeling.models.gpt,
                          api_key: String(value),
                        },
                      },
                    },
                  })
                }
              />
              <HeroInput
                label="API Base URL"
                value={settings.labeling.models.gpt.base_url}
                placeholder="https://api.openai.com/v1"
                onChange={(value) =>
                  updateSettings({
                    ...settings,
                    labeling: {
                      ...settings.labeling,
                      models: {
                        ...settings.labeling.models,
                        gpt: {
                          ...settings.labeling.models.gpt,
                          base_url: String(value),
                        },
                      },
                    },
                  })
                }
              />
              <HeroInput
                label="模型名称"
                value={settings.labeling.models.gpt.model_name}
                placeholder="gpt-4o"
                onChange={(value) =>
                  updateSettings({
                    ...settings,
                    labeling: {
                      ...settings.labeling,
                      models: {
                        ...settings.labeling.models,
                        gpt: {
                          ...settings.labeling.models.gpt,
                          model_name: String(value),
                        },
                      },
                    },
                  })
                }
              />
              <HeroInput
                label="最大 Token 数"
                type="number"
                min={1}
                value={settings.labeling.models.gpt.max_tokens}
                onChange={(value) =>
                  updateSettings({
                    ...settings,
                    labeling: {
                      ...settings.labeling,
                      models: {
                        ...settings.labeling.models,
                        gpt: {
                          ...settings.labeling.models.gpt,
                          max_tokens: Number(value) || 1000,
                        },
                      },
                    },
                  })
                }
              />
              <HeroInput
                label="Temperature"
                type="number"
                min={0}
                max={2}
                step={0.1}
                value={settings.labeling.models.gpt.temperature}
                onChange={(value) =>
                  updateSettings({
                    ...settings,
                    labeling: {
                      ...settings.labeling,
                      models: {
                        ...settings.labeling.models,
                        gpt: {
                          ...settings.labeling.models.gpt,
                          temperature: Number(value) || 0.7,
                        },
                      },
                    },
                  })
                }
              />
            </GroupCard>
            )}

            {settings.labeling.selected_model === "lm_studio" && (
            <GroupCard title="LM Studio 配置">
              <HeroInput
                label="API Base URL"
                value={settings.labeling.models.lm_studio.base_url}
                placeholder="http://127.0.0.1:1234/v1"
                onChange={(value) =>
                  updateSettings({
                    ...settings,
                    labeling: {
                      ...settings.labeling,
                      models: {
                        ...settings.labeling.models,
                        lm_studio: {
                          ...settings.labeling.models.lm_studio,
                          base_url: String(value),
                        },
                      },
                    },
                  })
                }
              />
              <HeroInput
                label="模型名称"
                value={settings.labeling.models.lm_studio.model_name}
                placeholder="local-model"
                onChange={(value) =>
                  updateSettings({
                    ...settings,
                    labeling: {
                      ...settings.labeling,
                      models: {
                        ...settings.labeling.models,
                        lm_studio: {
                          ...settings.labeling.models.lm_studio,
                          model_name: String(value),
                        },
                      },
                    },
                  })
                }
              />
            </GroupCard>
            )}
          </>
        )}
        </div>
      </div>
    </div>
  );
}

// 防抖函数
function debounce<T extends (...args: any[]) => any>(func: T, delay: number): T {
  let timeoutId: NodeJS.Timeout;
  return ((...args: Parameters<T>) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func(...args), delay);
  }) as T;
}
