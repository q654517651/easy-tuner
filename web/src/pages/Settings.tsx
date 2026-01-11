import React, { useState, useEffect, useCallback } from "react";
import { Tabs, Tab, addToast, Button, Spinner } from "@heroui/react";
import HeaderBar from "../ui/HeaderBar";
import GroupCard from "../ui/GroupCard";
import ScrollArea from "../ui/ScrollArea";
import { HeroInput, HeroSelect, HeroSwitch, HeroTextarea, type SelectOption } from "../ui/HeroFormControls";
import { getLocaleString } from "../utils/languageDetection";
import DynamicLabelingConfig from "../components/DynamicLabelingConfig";
import {
  buildModelGroups,
  getGroupedValue,
  setGroupedValue,
  getGroupDisplayTitle,
  isFullWidthField,
  type ModelPathsSchema,
  type GroupedModel
} from "../utils/modelGrouping";
import { getApiBaseUrl, fetchJson, postJson, readinessApi } from "../services/api";
import RuntimeInstallModal from "../components/RuntimeInstallModal";
import WorkspaceSelectModal from "../components/WorkspaceSelectModal";
import { debounce } from "../utils/debounce";
import { getNestedValue as getNestedValueUtil, setNestedValue as setNestedValueUtil } from "../utils/object";

// Types are now imported from modelGrouping.ts

// ============================
// 类型定义
// ============================

// Musubi 配置类型（简化后，仅保留基本信息）
interface MusubiConfig {
  status: "installed" | "not_found" | "error";
  message?: string;
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
      <Spinner size="lg" color="primary" />
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
  const [modelPathsSchema, setModelPathsSchema] = useState<ModelPathsSchema | null>(null);
  const [showRuntimeModal, setShowRuntimeModal] = useState(false);
  const [showWorkspaceModal, setShowWorkspaceModal] = useState(false);
  const [workspacePath, setWorkspacePath] = useState<string>("");

  // 防抖保存函数
  const debouncedSave = useCallback(
    debounce(async (settings: AppSettings) => {
      try {
        setSaving(true);

        const response = await fetch(`${getApiBaseUrl()}/settings`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(settings),
        });

        const result = await response.json();
        if (result.success) {
          addToast({
            title: "已保存",
            color: "success",
            timeout: 1500
          });
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

      const result = await fetchJson<any>("/settings");
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
  // 使用统一的工具函数（从 utils/object.ts 导入）
  const getNestedValue = (obj: any, path: string): string => {
    return getNestedValueUtil(obj, path, "");
  };

  const setNestedValue = (obj: any, path: string, value: string) => {
    return setNestedValueUtil(obj, path, value);
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
      const result = await fetchJson<any>("/settings/model-paths/schema");
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
  }, []);

  // 初始化获取当前工作区路径
  useEffect(() => {
    (async () => {
      try {
        const ws = await readinessApi.getWorkspaceStatus();
        setWorkspacePath(ws?.data?.path || "");
      } catch {}
    })();
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
    <div className="flex flex-col h-full min-h-0">
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
          <Tab key="基础设置" title="基础设置" />
        </Tabs>
      </div>

      <ScrollArea className="flex-1 min-h-0">
        <div className="px-5 pb-5 space-y-6">


        {/* 后端状态 */}
        {activeTab === "后端状态" && (
          <div className="h-full flex flex-col space-y-6">
            <GroupCard
              title="训练环境"
              headerContent={
                <Button
                  color="warning"
                  variant="light"
                  size="sm"
                  onPress={() => setShowRuntimeModal(true)}
                  isLoading={false}
                >
                  安装/修复训练环境
                </Button>
              }
            >
              <div className="md:col-span-2">
                <div className="text-sm text-gray-600 dark:text-gray-300">
                  训练器已作为应用内置组件打包，无需额外安装。
                  <br />
                  如果遇到训练环境问题，可以点击上方按钮重新安装或修复环境。
                </div>
              </div>
            </GroupCard>
          </div>
        )}

        {/* 模型路径 - 按组分组显示 */}
        {activeTab === "模型路径" && (
          <>
            {!modelPathsSchema ? (
              <div className="flex items-center justify-center py-8">
                <div className="text-gray-600">加载模型路径配置中...</div>
              </div>
            ) : (
              buildModelGroups(modelPathsSchema).map((group) => {
                // 先渲染共享字段，再渲染所有模型的 dit 字段
                const sharedFields = group.models[0]?.allFields.filter(f => !isFullWidthField(f.key)) || [];
                const ditFields = group.models.flatMap(model =>
                  model.allFields
                    .filter(f => isFullWidthField(f.key))
                    .map(field => ({ model, field }))
                );

                return (
                  <GroupCard key={group.groupKey} title={getGroupDisplayTitle(group.groupKey)}>
                    {/* 共享字段小标题 */}
                    {sharedFields.length > 0 && (
                      <div className="md:col-span-2">
                        <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
                          共享组件路径
                        </h4>
                      </div>
                    )}

                    {/* 1. 先显示共享字段（vae, text_encoder 等） */}
                    {sharedFields.map((field) => {
                      const currentValue = getGroupedValue(
                        settings,
                        group.groupKey,
                        group.models[0].typeName,
                        field.key,
                        field.setting_path
                      );

                      return (
                        <div key={field.key}>
                          <HeroInput
                            label={field.label}
                            value={currentValue}
                            onChange={(value) => {
                              const newSettings = setGroupedValue(
                                settings,
                                group.groupKey,
                                group.models[0].typeName,
                                field.key,
                                field.setting_path,
                                String(value),
                                group.models
                              );
                              updateSettings(newSettings);
                            }}
                            placeholder={field.help || `请输入${field.label}`}
                          />
                        </div>
                      );
                    })}

                    {/* 独占字段小标题 */}
                    {ditFields.length > 0 && (
                      <div className="md:col-span-2">
                        <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2 mt-2">
                          模型专属路径
                        </h4>
                      </div>
                    )}

                    {/* 2. 再显示所有模型的 dit 字段 */}
                    {ditFields.map(({ model, field }) => {
                      const fieldLabel = group.models.length > 1
                        ? `${model.title} - ${field.label}`
                        : field.label;

                      return (
                        <div key={`${model.typeName}-${field.key}`} className="md:col-span-2">
                          <HeroInput
                            label={fieldLabel}
                            value={getGroupedValue(
                              settings,
                              group.groupKey,
                              model.typeName,
                              field.key,
                              field.setting_path
                            )}
                            onChange={(value) => {
                              const newSettings = setGroupedValue(
                                settings,
                                group.groupKey,
                                model.typeName,
                                field.key,
                                field.setting_path,
                                String(value),
                                group.models
                              );
                              updateSettings(newSettings);
                            }}
                            placeholder={field.help || `请输入${field.label}`}
                            help={field.help}
                          />
                        </div>
                      );
                    })}
                  </GroupCard>
                );
              })
            )}
          </>
        )}

        {/* 打标设置 */}
        {activeTab === "打标设置" && (
          <DynamicLabelingConfig
            settings={settings}
            onUpdate={updateSettings}
          />
        )}
        {/* 基础设置 */}
        {activeTab === "基础设置" && (
          <div className="h-full flex flex-col space-y-6">
            <GroupCard title="工作区" noGrid>
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm opacity-80 truncate">
                  当前路径：{workspacePath || '未设置'}
                </div>
                <Button size="sm" variant="bordered" onPress={() => setShowWorkspaceModal(true)}>
                  设置工作区
                </Button>
              </div>
            </GroupCard>
          </div>
        )}
        </div>
      </ScrollArea>
      {/* 安装/修复训练环境弹窗复用 RuntimeInstallModal */}
      <RuntimeInstallModal
        isOpen={showRuntimeModal}
        onClose={() => setShowRuntimeModal(false)}
        onSuccess={() => {
          setShowRuntimeModal(false);
          // 完成后刷新设置状态，显示最新环境信息
          loadSettings();
        }}
      />
      {/* 工作区选择弹窗 */}
      <WorkspaceSelectModal
        isOpen={showWorkspaceModal}
        onClose={() => setShowWorkspaceModal(false)}
        onSuccess={async () => {
          setShowWorkspaceModal(false);
          try {
            const ws = await readinessApi.getWorkspaceStatus();
            setWorkspacePath(ws?.data?.path || "");
          } catch {}
        }}
      />
    </div>
  );
}

// debounce 函数已从 utils/debounce.ts 导入
