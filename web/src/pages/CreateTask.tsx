/**
 * CreateTask.tsx
 * -----------------------------------------------------------------------------
 * 「模型注册表驱动」的创建训练页面
 *
 * 前后端协议（约定）：
 *
 * 1) 模型列表
 *    GET /api/models
 *    -> Array<{ type_name: string; title: string }>
 *
 * 2) 单模型规范
 *    GET /api/models/{type_name}
 *    -> ModelSpec:
 *       { type_name, title, script_train?: string, group_order: string[], fields: FieldSpec[] }
 *       FieldSpec: { name: string; default: any; meta?: FieldMeta }
 *       FieldMeta:
 *         - label?: string
 *         - group?: string
 *         - widget?: "text"|"textarea"|"number"|"select"|"checkbox"|"path"|"multiselect"
 *         - placeholder?: string
 *         - min/max/step?: number
 *         - enum?: {label,value}[]
 *         - enable_if?: Array<[key, cond]>
 *         - cli?: { flag?: string; fmt?: string; fmt_args?: string[]; skip_if_empty?: boolean }
 *
 * 3) 训练任务创建
 *    POST /api/tasks
 *    body: { training_type: string; values: Record<string, any> }
 *    -> { task_id: string }
 *
 * 4) 其他系统数据（此页仅展示）
 *    - GPU 列表：GET /api/system/gpus  -> string[]
 *    - 数据集列表：GET /api/datasets   -> Array<{id:string; name:string}>
 *
 * 容错：
 *  - 无 meta/group → 归入 "advanced"
 *  - 无 enable_if → 默认可见
 *  - 无 cli → 默认 "--name value"（boolean 为 "--name"）
 *  - 未识别 widget → text
 * -----------------------------------------------------------------------------
 */

import React, { useEffect, useMemo, useRef, useState, startTransition } from "react";

// 工具函数：基于getBoundingClientRect计算准确的滚动目标位置
function topIn(container: HTMLElement, el: HTMLElement, extra = 0) {
  const c = container.getBoundingClientRect();
  const e = el.getBoundingClientRect();
  return container.scrollTop + (e.top - c.top) - extra;  // extra=滚动预留
}
import { Skeleton, Tabs, Tab, addToast, Button } from "@heroui/react";
import ScrollArea from "../ui/ScrollArea";
import HeaderBar from "../ui/HeaderBar";
import {
  HeroInput,
  HeroSelect,
  HeroSwitch,
  HeroTextarea,
  HERO_RESOLUTION_OPTIONS,
  convertToHeroOptions,
  type SelectOption
} from "../ui/HeroFormControls";
import GroupCard from "../ui/GroupCard";
import { trainingApi, API_BASE_URL } from "../services/api";
// import { BigInput, BigSelect, SwitchTile } from "../ui/Input";

/* ========= 类型定义 ========= */
// EnumItem类型已由SelectOption替代
type EnableCond =
  | any
  | {
      not?: any;
      in?: any[];
      nin?: any[];
      gt?: number;
      gte?: number;
      lt?: number;
      lte?: number;
      truthy?: true;
      falsy?: true;
    };

// 后端返回的数据结构
type TrainingGroup = {
  key: string;
  title: string;
  description: string;
};

type TrainingField = {
  name: string;
  label: string;
  widget: string;
  help: string;
  group: string;
  value: any;
  default_value: any;
  options?: any[];
  min_value?: number;
  max_value?: number;
  step?: number;
  enable_if?: Record<string, any>;
};

type TrainingModelSpec = {
  type_name: string;
  title: string;
  script_train: string;
  script_cache_te: string;
  script_cache_latents: string;
  network_module: string;
  group_order: string[];
  path_mapping: Record<string, string>;
};

type TrainingConfigSchema = {
  groups: TrainingGroup[];
  fields: TrainingField[];
  model_spec: TrainingModelSpec;
};

// 兼容性类型 (旧的前端代码使用)
type FieldSpec = { name: string; default: any; meta?: any };
type ModelSpec = TrainingConfigSchema;

type ModelSummary = {
  type_name: string;
  title: string;
  supported_dataset_types?: string[];
  script_train?: string;
  script_cache_te?: string | null;
  script_cache_latents?: string | null;
  network_module?: string;
  group_order?: string[];
  path_mapping?: Record<string, string>;
};
type DsItem = { id: string; name: string; type?: string };

// 页面级缓存
let _modelsCache: ModelSummary[] | null = null;
let _gpusCache: string[] | null = null;
let _datasetsCache: DsItem[] | null = null;

/* ========= 条件显隐 & CLI ========= */
function checkCond(value: any, cond: EnableCond): boolean {
  if (cond && typeof cond === "object" && !Array.isArray(cond)) {
    if ("not" in cond) return value !== (cond as any).not;
    if ("in" in cond) return Array.isArray((cond as any).in) && (cond as any).in.includes(value);
    if ("nin" in cond) return Array.isArray((cond as any).nin) && !(cond as any).nin.includes(value);
    if ("gt" in cond) return typeof value === "number" && value > (cond as any).gt;
    if ("gte" in cond) return typeof value === "number" && value >= (cond as any).gte;
    if ("lt" in cond) return typeof value === "number" && value < (cond as any).lt;
    if ("lte" in cond) return typeof value === "number" && value <= (cond as any).lte;
    if ("truthy" in cond) return !!value;
    if ("falsy" in cond) return !value;
  }
  return value === cond;
}
function enabledBy(meta: FieldMeta | undefined, values: Record<string, any>): boolean {
  const enable_if = meta?.enable_if;
  if (!enable_if) return true;
  
  // 支持对象格式：{"scheduler__in": ["cosine", "linear"], "warmup_mode": "steps"}
  if (typeof enable_if === 'object' && !Array.isArray(enable_if)) {
    return Object.entries(enable_if).every(([key, cond]) => {
      // 处理操作符后缀，如 scheduler__in
      if (key.endsWith('__in')) {
        const fieldName = key.slice(0, -4);  // 去掉 __in
        return checkCond(values[fieldName], { in: cond });
      }
      // 直接相等比较
      return checkCond(values[key], cond);
    });
  }
  
  // 兼容旧的数组格式（如果存在）
  if (Array.isArray(enable_if)) {
    return enable_if.every(([k, c]) => checkCond(values[k], c));
  }
  
  return true;
}
function template(fmt: string, dict: Record<string, any>): string {
  return fmt.replace(/\{(\w+)\}/g, (_, k) => {
    const v = dict[k];
    return v === undefined || v === null ? "" : String(v);
  });
}
// buildCliArgs 函数已删除，现在使用后端API预览

/* ========= UI 基元 ========= */

/* ========= 页面主体 ========= */
export default function CreateTask() {
  const [models, setModels] = useState<ModelSummary[]>(_modelsCache ?? []);
  const [typeName, setTypeName] = useState<string>("");
  const [model, setModel] = useState<ModelSpec | null>(null);
  const [modelLoading, setModelLoading] = useState<boolean>(false);
  const modelReqIdRef = useRef(0);
  const [values, setValues] = useState<Record<string, any>>({});
  const [error, setError] = useState<string | null>(null);

  // 仅展示：GPU 列表、数据集列表（有接口则用，无则给占位）
  const [gpus, setGpus] = useState<string[]>(_gpusCache ?? []);
  const [datasets, setDatasets] = useState<DsItem[]>(_datasetsCache ?? []);
  const [gpusLoading, setGpusLoading] = useState<boolean>(_gpusCache === null);
  const [datasetsLoading, setDatasetsLoading] = useState<boolean>(_datasetsCache === null);

  // 获取当前选择的模型信息（用于兼容性校验）
  const selectedModel = models.find(m => m.type_name === typeName);
  const supportedDatasetTypes = selectedModel?.supported_dataset_types || [];


  // 导航和滚动相关状态
  const [activeTab, setActiveTab] = useState<string>("任务设置");
  const scrollRef = useRef<HTMLDivElement>(null);
  const anchorRefs = useRef<Record<string, HTMLElement | null>>({});
  const isScrollingProgrammatically = useRef<boolean>(false);
  const tabClickTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isTabChanging = useRef<boolean>(false);

  // ref注册辅助函数
  const registerRef = (id: string, element: HTMLDivElement | null) => {
    anchorRefs.current[id] = element;
  };

  // 拉模型列表
  useEffect(() => {
    if (_modelsCache) {
      // 有缓存时直接使用，并设置typeName
      if (_modelsCache.length && !typeName) {
        const savedType = localStorage.getItem("tt_last_type") || "";
        const exists = _modelsCache.some(m => m.type_name === savedType);
        setTypeName(exists ? savedType : _modelsCache[0].type_name);
      }
      return; // 有缓存就不再请求
    }

    fetch(`${API_BASE_URL}/training/models`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((response) => {
        const list: ModelSummary[] = response.data;
        _modelsCache = list; // 写入缓存
        setModels(list);
        if (list.length && !typeName) {
          const savedType = localStorage.getItem("tt_last_type") || "";
          const exists = list.some(m => m.type_name === savedType);
          setTypeName(exists ? savedType : list[0].type_name);
        }
      })
      .catch((e) => setError("加载模型列表失败：" + e.message));
  }, []);

  // 拉模型规范（保留旧内容 + 仅采纳最新响应）
  useEffect(() => {
    if (!typeName) return;
    setError(null);
    setModelLoading(true);
    const reqId = ++modelReqIdRef.current;

    // 先尝试使用本地缓存，立即呈现，减少首次跳动
    try {
      const specKey = `tt_model_spec:${typeName}`;
      const valuesKey = `tt_values:${typeName}`;
      const cachedSpecStr = localStorage.getItem(specKey);
      if (cachedSpecStr) {
        const cachedSpec: TrainingConfigSchema = JSON.parse(cachedSpecStr);
        const cachedValuesStr = localStorage.getItem(valuesKey);
        const cachedValues = cachedValuesStr ? JSON.parse(cachedValuesStr) : undefined;
        startTransition(() => {
          setModel(cachedSpec);
          if (cachedValues) setValues(cachedValues);
        });
      }
    } catch {}

    fetch(`${API_BASE_URL}/training/config/${encodeURIComponent(typeName)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((response) => {
        if (reqId !== modelReqIdRef.current) return; // 非最新响应则忽略
        const spec: TrainingConfigSchema = response.data;
        const init: Record<string, any> = {};
        for (const f of spec.fields) init[f.name] = f.value; // 使用value而不是default_value，这样可以获取从设置中加载的路径
        startTransition(() => {
          setModel(spec);
          setValues(init);
        });
        try {
          localStorage.setItem(`tt_model_spec:${typeName}`, JSON.stringify(spec));
          localStorage.setItem(`tt_values:${typeName}`, JSON.stringify(init));
        } catch {}
      })
      .catch((e) => {
        if (reqId !== modelReqIdRef.current) return;
        setError("加载模型规范失败：" + e.message);
      })
      .finally(() => {
        if (reqId === modelReqIdRef.current) setModelLoading(false);
      });
  }, [typeName]);

  // 记录最近一次选择的训练类型
  useEffect(() => {
    if (typeName) localStorage.setItem("tt_last_type", typeName);
  }, [typeName]);

  // 变更 values 时同步缓存，便于下次冷启动直接加载上次内容，减少首次跳动
  useEffect(() => {
    if (!typeName) return;
    try {
      localStorage.setItem(`tt_values:${typeName}`, JSON.stringify(values));
    } catch {}
  }, [values, typeName]);

  // 拉 GPU / 数据集（仅展示）
  useEffect(() => {
    // GPU数据获取
    if (_gpusCache === null) {
      fetch(`${API_BASE_URL}/system/gpus`)
        .then((r) => (r.ok ? r.json() : Promise.reject()))
        .then((response) => {
          const gpuList = response.data || [];
          _gpusCache = gpuList; // 写入缓存
          setGpus(gpuList);
        })
        .catch(() => {
          const emptyList: string[] = [];
          _gpusCache = emptyList; // 缓存空数组，避免重复请求
          setGpus(emptyList);
        })
        .finally(() => setGpusLoading(false));
    }

    // 数据集数据获取
    if (_datasetsCache === null) {
      fetch(`${API_BASE_URL}/datasets`)
        .then((r) => (r.ok ? r.json() : Promise.reject()))
        .then((response) => {
          const datasetList = response.data || [];
          _datasetsCache = datasetList; // 写入缓存
          setDatasets(datasetList);
        })
        .catch(() => {
          const emptyList: DsItem[] = [];
          _datasetsCache = emptyList; // 缓存空数组，避免重复请求
          setDatasets(emptyList);
        })
        .finally(() => setDatasetsLoading(false));
    }
  }, []);

  const gateReady = Boolean(model) && !gpusLoading && !datasetsLoading;

  // 延迟展示骨架，避免有缓存时的闪烁
  const [showSkeleton, setShowSkeleton] = useState(false);
  useEffect(() => {
    if (gateReady) {
      setShowSkeleton(false);
      return;
    }
    // 只有在100ms后还没ready才显示骨架屏
    const t = window.setTimeout(() => setShowSkeleton(true), 100);
    return () => window.clearTimeout(t);
  }, [gateReady]);

  // 导航定义 - 提前定义以便在多处使用
  const sectionDefs: { id: string; title: string }[] = [
    { id: "sec_task", title: "任务设置" },
    { id: "sec_dataset", title: "数据集设置" },
    ...(model?.groups?.filter(g => g.key !== "dataset").map((g) => ({
      id: `sec_${g.key}`,
      title: g.title,
    })) ?? []),
  ];

  // 滚动监听 - 页面滚动时自动切换导航
  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;

    const handleScroll = () => {
      if (isScrollingProgrammatically.current) return;

      const cRect = container.getBoundingClientRect();
      const sections = sectionDefs.map(s => {
        const el = anchorRefs.current[s.id];
        if (!el) return null;
        const top = el.getBoundingClientRect().top - cRect.top + container.scrollTop;
        return { title: s.title, top };
      }).filter(Boolean) as {title:string; top:number}[];

      // 找到当前滚动位置对应的section
      const y = container.scrollTop + 100;  // 缓冲区
      let currentSection = sections[0]?.title || "任务设置";
      for (let i = sections.length - 1; i >= 0; i--) {
        if (y >= sections[i].top) {
          currentSection = sections[i].title;
          break;
        }
      }

      if (currentSection !== activeTab) {
        setActiveTab(currentSection);
      }
    };

    container.addEventListener('scroll', handleScroll, { passive: true });
    return () => container.removeEventListener('scroll', handleScroll);
  }, [activeTab, model]);

  // 清理定时器
  useEffect(() => {
    return () => {
      if (tabClickTimeoutRef.current) {
        clearTimeout(tabClickTimeoutRef.current);
      }
    };
  }, []);

  // 预览数据状态
  const [previewData, setPreviewData] = useState<{
    command?: string;
    toml_content?: string;
    toml_path?: string;
    bat_script?: string;
    script_path?: string;
    working_directory?: string;
  } | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [displayPreview, setDisplayPreview] = useState<{
    command?: string;
    toml_content?: string;
    toml_path?: string;
    bat_script?: string;
    script_path?: string;
    working_directory?: string;
  } | null>(null);
  const previewReqIdRef = useRef(0);
  // 预览相关引用（简化后不再需要复杂的高度动画）

  // 获取后端预览
  const fetchPreview = async () => {
    if (!model) return;

    // 如果没有选择数据集，使用第一个可用数据集或默认值
    const datasetId = values.__dataset_id || datasets[0]?.id || "preview_dataset";


    setPreviewLoading(true);
    const reqId = ++previewReqIdRef.current;
    try {
      // 过滤掉内部字段（以__开头的字段）
      const cleanConfig = Object.fromEntries(
        Object.entries(values).filter(([key]) => !key.startsWith('__'))
      );

      const requestData = {
        training_type: model.model_spec.type_name,
        config: cleanConfig,
        dataset_id: datasetId,
        output_dir: `workspace/trainings/${Date.now()}`
      };

      console.log('[CreateTask] 开始预览 CLI 命令:', requestData);
      const response = await trainingApi.previewCliCommand(requestData);
      console.log('[CreateTask] 预览 CLI 响应:', response);
      if (reqId === previewReqIdRef.current) {
        setPreviewData(response);
        setDisplayPreview(response);
      }
    } catch (error) {
      // 失败时保留旧的 displayPreview，不清空
      console.error('[CreateTask] 预览 CLI 失败:', error);
    } finally {
      if (reqId === previewReqIdRef.current) setPreviewLoading(false);
    }
  };

  // 监听配置变化，自动更新预览
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchPreview();
    }, 500); // 防抖

    return () => clearTimeout(timer);
  }, [values, model, datasets]); // 添加datasets依赖，数据集加载后也更新预览

  // CLI 预览行（保留旧内容，加载时不闪空）
  const cliLines = useMemo(() => {
    if (!displayPreview?.command) {
      return ["配置参数以查看预览"];
    }
    const parts = displayPreview.command.split(' ');
    const formatted: string[] = [];
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      if (part.startsWith('--') && i + 1 < parts.length && !parts[i + 1].startsWith('--')) {
        formatted.push(`${part} ${parts[i + 1]}`);
        i++;
      } else {
        formatted.push(part);
      }
    }
    return formatted;
  }, [displayPreview, previewLoading]);

  const groups = model?.model_spec?.group_order ?? [];
  const visible = (f: TrainingField) => (model ? enabledBy({ enable_if: f.enable_if }, values) : false);

  const submitTask = async () => {
    if (!model) return;

    // 检查必要的字段
    const taskName = values.__task_name?.trim() || `${model.model_spec.title}_${new Date().toISOString().slice(0, 19).replace(/[:-]/g, '')}`;
    const datasetId = values.__dataset_id || datasets[0]?.id; // 使用相同的默认值逻辑

    if (!datasetId) {
      addToast({
        title: "创建失败",
        description: "请选择数据集",
        color: "warning",
        timeout: 3000
      });
      return;
    }

    try {
      // 过滤掉内部字段（以__开头的字段）
      const cleanConfig = Object.fromEntries(
        Object.entries(values).filter(([key]) => !key.startsWith('__'))
      );

      const requestData = {
        name: taskName,
        dataset_id: datasetId,
        training_type: model.model_spec.type_name,
        config: cleanConfig
      };

      const res = await fetch(`${API_BASE_URL}/training/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestData),
      });

      if (!res.ok) {
        let errorMessage = `HTTP ${res.status}`;
        try {
          const errorData = await res.json();
          errorMessage = errorData.message || errorData.detail || errorMessage;
        } catch {
          // 如果无法解析JSON，使用默认错误消息
        }
        throw new Error(errorMessage);
      }

      const response = await res.json();
      const taskId = response.data?.task_id || response.data || "unknown";
      addToast({
        title: "创建成功",
        description: `任务ID：${taskId}`,
        color: "success",
        timeout: 3000
      });
    } catch (e: any) {
      const errorMessage = e?.message || String(e) || "未知错误";
      addToast({
        title: "创建失败",
        description: errorMessage,
        color: "danger",
        timeout: 3000
      });
    }
  };

  // 删除重复的sectionDefs定义，已在上面定义

  // 导航点击处理 - 根据title查找对应的section并滚动 (带防抖)
  const handleTabChange = (title: string) => {
    // 如果正在处理tab切换，忽略新的点击
    if (isTabChanging.current) return;

    const container = scrollRef.current;
    if (!container) return;

    // 清除之前的防抖定时器
    if (tabClickTimeoutRef.current) {
      clearTimeout(tabClickTimeoutRef.current);
    }

    // 立即更新tab状态，避免视觉延迟
    setActiveTab(title);

    // 防抖处理滚动操作
    tabClickTimeoutRef.current = setTimeout(() => {
      // 根据title找到对应的section id
      const section = sectionDefs.find(s => s.title === title);
      if (!section) return;

      const el = anchorRefs.current[section.id];
      if (el) {
        isTabChanging.current = true;
        isScrollingProgrammatically.current = true;

        // 使用更准确的滚动位置计算
        container.scrollTo({
          top: topIn(container, el, 12),
          behavior: "smooth",
        });

        // 滚动完成后重新启用滚动监听和tab点击
        setTimeout(() => {
          isScrollingProgrammatically.current = false;
          isTabChanging.current = false;
        }, 500);
      }
    }, 50); // 50ms防抖延迟
  };

  // 字段渲染函数 - 支持后端返回的widget类型
  const renderField = (f: TrainingField) => {
    const label = f.label;

    // Switch类型控件 (checkbox/switch)
    if (f.widget === "switch") {
      return (
        <HeroSwitch
          key={f.name}
          label={label}
          checked={!!values[f.name]}
          description={f.help}
          onChange={(v) => setValues((s) => ({ ...s, [f.name]: v }))}
          className="col-span-1"
        />
      );
    }

    // 下拉选择框 (dropdown/select)
    if (f.widget === "dropdown") {
      const options: SelectOption[] = f.options?.map(opt => ({ label: opt, value: opt })) ?? [];
      return (
        <HeroSelect
          key={f.name}
          label={label}
          value={values[f.name]}
          options={options}
          placeholder={f.help}
          onChange={(v) => setValues((s) => ({ ...s, [f.name]: v }))}
        />
      );
    }

    // 文本区域
    if (f.widget === "textarea") {
      return (
        <HeroTextarea
          key={f.name}
          label={label}
          value={values[f.name] || ""}
          placeholder={f.help}
          rows={4}
          onChange={(v) => setValues((s) => ({ ...s, [f.name]: v }))}
          className="col-span-1"
        />
      );
    }

    // 数字输入框
    if (f.widget === "number" || f.widget === "number_float") {
      return (
        <HeroInput
          key={f.name}
          label={label}
          value={values[f.name]}
          placeholder={f.help}
          type="number"
          min={f.min_value}
          max={f.max_value}
          step={f.step}
          onChange={(v) => setValues((s) => ({ ...s, [f.name]: v === "" ? "" : Number(v) }))}
        />
      );
    }

    // 分辨率选择器 (特殊控件)
    if (f.widget === "resolution_selector") {
      return (
        <HeroSelect
          key={f.name}
          label={label}
          value={values[f.name]}
          options={HERO_RESOLUTION_OPTIONS}
          placeholder={f.help}
          onChange={(v) => setValues((s) => ({ ...s, [f.name]: v }))}
        />
      );
    }

    // 文件选择器 (暂时用文本输入框)
    if (f.widget === "file_picker") {
      return (
        <HeroInput
          key={f.name}
          label={label}
          value={values[f.name]}
          placeholder={f.help}
          type="text"
          onChange={(v) => setValues((s) => ({ ...s, [f.name]: v }))}
        />
      );
    }

    // 默认文本输入框
    return (
      <HeroInput
        key={f.name}
        label={label}
        value={values[f.name]}
        placeholder={f.help}
        type="text"
        onChange={(v) => setValues((s) => ({ ...s, [f.name]: v }))}
      />
    );
  };

  return (
    <div className="flex flex-col h-full min-h-0 overflow-hidden">
      {/* 顶栏（不滚动） */}
      <HeaderBar
        crumbs={[
          { label: "任务管理", path: "/tasks" },
          { label: "创建训练任务" }
        ]}
        actions={
          <Button
            onClick={submitTask}
            color="primary"
            size="sm"
            startContent="🔵"
          >
            创建任务
          </Button>
        }
      />

      {/* 导航栏 */}
      <div className="h-[72px] shrink-0 bg-white/40 dark:bg-black/10 backdrop-blur px-4 flex items-center justify-between">
        <Tabs
          selectedKey={activeTab}
          onSelectionChange={(key) => handleTabChange(key as string)}
          variant="solid"
        >
          {sectionDefs.map((section) => (
            <Tab key={section.title} title={section.title} />
          ))}
        </Tabs>
      </div>

      {/* 主体：左右两列布局 */}
      <div className="flex-1 min-h-0 overflow-hidden px-5 pb-5 flex gap-5">
        {/* 左列：设置区域 */}
        <div className="flex-1 min-h-0">
          <ScrollArea
            scrollerRef={scrollRef}
            className="h-full min-h-0 pl-px pt-px"
            style={{ scrollPaddingTop: 20 }}
          >
            <div className={gateReady ? "" : "relative"}>
            {error && <div className="text-[14px] text-red-600">{error}</div>}

            {/* 骨架屏层 - 绝对定位覆盖，调整位置匹配实际内容 */}
            {!gateReady && showSkeleton && (
            <div className="absolute top-0 left-0 right-3 bottom-0 space-y-5">
              <div className="rounded-2xl ring-1 ring-black/5 dark:ring-white/10 p-6">
                <div className="mb-4"><Skeleton className="h-4 w-32 rounded-md" /></div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Skeleton className="h-[88px] rounded-2xl" />
                  <Skeleton className="h-[88px] rounded-2xl" />
                </div>
              </div>
              <div className="rounded-2xl ring-1 ring-black/5 dark:ring-white/10 p-6">
                <div className="mb-4"><Skeleton className="h-4 w-32 rounded-md" /></div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Skeleton className="h-[88px] rounded-2xl" />
                  <Skeleton className="h-[88px] rounded-2xl" />
                </div>
              </div>
              {[0,1,2].map(i => (
                <div key={i} className="rounded-2xl ring-1 ring-black/5 dark:ring-white/10 p-6">
                  <div className="mb-4"><Skeleton className="h-4 w-40 rounded-md" /></div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Skeleton className="h-[88px] rounded-2xl" />
                    <Skeleton className="h-[88px] rounded-2xl" />
                    <Skeleton className="h-[88px] rounded-2xl" />
                    <Skeleton className="h-[88px] rounded-2xl" />
                  </div>
                </div>
              ))}
            </div>
            )}

            {/* 实际内容层 */}
            <div className={["space-y-5 pb-24 transition-opacity duration-300 ease-out", gateReady ? "opacity-100" : "opacity-0"].join(" ")}>
              <div ref={(el) => registerRef("sec_task", el)}>
                <GroupCard title="任务设置" anchorId="sec_task">
                  <HeroSelect
                    label="选择训练类型"
                    value={typeName}
                    options={models.map((m) => ({ label: m.title, value: m.type_name }))}
                    onChange={(v) => {
                      localStorage.setItem("tt_last_type", String(v));
                      setTypeName(v);
                    }}
                  />
                  <HeroInput
                    label="任务名称"
                    value={values.__task_name || ""}
                    placeholder={`${model?.model_spec?.title || "训练任务"}_${new Date().toISOString().slice(0, 19).replace(/[:-]/g, '')}`}
                    type="text"
                    onChange={(v) => setValues((s) => ({ ...s, __task_name: v }))}
                  />
                  <HeroSelect
                    label="GPU 设置（仅展示）"
                    value={gpus[0] ?? ""}
                    options={
                      (gpus.length
                        ? gpus
                        : ["未检测到 GPU"]
                      ).map((name, i) => ({ label: name, value: name || `gpu_${i}` }))
                    }
                    onChange={() => {}}
                  />
                </GroupCard>
              </div>

              <div ref={(el) => registerRef("sec_dataset", el)}>
                <GroupCard title="数据集设置" anchorId="sec_dataset">
                  <HeroSelect
                    label="选择数据集"
                    value={values.__dataset_id ?? (datasets[0]?.id ?? "")}
                    options={
                      (datasets.length
                        ? datasets.map((d) => ({
                            label: d.name,
                            value: d.id
                          }))
                        : [{ label: "暂未检测到数据集", value: "" }]
                      )
                    }
                    disabledKeys={(() => {
                      return supportedDatasetTypes.length > 0
                        ? datasets
                            .filter((d) => d.type && !supportedDatasetTypes.includes(d.type))
                            .map((d) => d.id)
                        : [];
                    })()}
                    onChange={(v) => setValues((s) => ({ ...s, __dataset_id: v }))}
                    description={supportedDatasetTypes.length > 0 ? `支持的数据集类型: ${supportedDatasetTypes.join(", ")}` : undefined}
                  />
                  {/* 显示dataset组的字段，主要是repeats */}
                  {model &&
                    model.fields
                      .filter((f) => f.group === "dataset" && visible(f))
                      .map((f) => renderField(f))}
                </GroupCard>
              </div>

              {model &&
                sectionDefs
                  .filter((s) => s.id.startsWith("sec_") && !["sec_task", "sec_dataset"].includes(s.id))
                  .map((sec) => {
                    const gKey = sec.id.replace(/^sec_/, "");
                    const fields = model.fields.filter((f) => f.group === gKey && visible(f));
                    if (!fields.length) return null;
                    return (
                      <div key={sec.id} ref={(el) => registerRef(sec.id, el)}>
                        <GroupCard title={sec.title} anchorId={sec.id}>
                          {fields.map((f) => renderField(f))}
                        </GroupCard>
                      </div>
                    );
                  })}
            </div>
            </div>
          </ScrollArea>
        </div>

        {/* 右列：训练脚本预览 */}
        <div className="w-[420px] shrink-0 hidden lg:flex flex-col gap-4">
            {/* 训练脚本预览 - 70%高度 */}
            <div className="rounded-2xl p-6 flex flex-col" style={{ height: 'calc(70% - 8px)', backgroundColor: 'var(--bg2)' }}>
              <div className="text-[14px] font-semibold mb-4 shrink-0">
                训练脚本 (train script)
              </div>
              <div className="flex-1 min-h-0 rounded-xl [border-width:1.5px] border-black/10 dark:border-white/5 bg-white dark:bg-[#2A2A2A] overflow-hidden">
                <ScrollArea className="h-full">
                  {!displayPreview?.command ? (
                    <div className="p-3 space-y-2">
                      <Skeleton className="h-4 w-[85%] rounded" />
                      <Skeleton className="h-4 w-[90%] rounded" />
                      <Skeleton className="h-4 w-[80%] rounded" />
                      <Skeleton className="h-4 w-[70%] rounded" />
                      <Skeleton className="h-4 w-[60%] rounded" />
                    </div>
                  ) : (
                    <pre className={`text-[12px] whitespace-pre leading-5 font-mono p-3 ${previewLoading ? "opacity-70" : "opacity-100"}`}>
                      {cliLines.length ? cliLines.join("\n") : "…"}
                    </pre>
                  )}
                </ScrollArea>
              </div>
            </div>

            {/* 数据集配置预览 - 30%高度 */}
            <div className="rounded-2xl p-6 flex flex-col" style={{ height: 'calc(30% - 8px)', backgroundColor: 'var(--bg2)' }}>
              <div className="text-[14px] font-semibold mb-4 shrink-0">
                数据集配置 (dataset.toml)
              </div>
              <div className="flex-1 min-h-0 rounded-xl [border-width:1.5px] border-black/10 dark:border-white/5 bg-white dark:bg-[#2A2A2A] overflow-hidden">
                <ScrollArea className="h-full">
                  {displayPreview?.toml_content ? (
                    <pre className="text-[12px] whitespace-pre leading-5 font-mono p-3">
                      {displayPreview.toml_content}
                    </pre>
                  ) : (
                    <div className="p-3 text-[12px] text-gray-500">
                      等待配置加载...
                    </div>
                  )}
                </ScrollArea>
              </div>
            </div>
        </div>
      </div>
    </div>
  );
}
