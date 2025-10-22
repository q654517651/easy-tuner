// src/services/api.ts
// 统一 API 基址解析：
// 优先级：VITE_API_BASE -> VITE_API_BASE_URL -> window.__API_BASE__ -> 动态端口 -> 127.0.0.1:8000
const RAW_BASE =
  ((import.meta as any)?.env?.VITE_API_BASE as string | undefined) ||
  ((import.meta as any)?.env?.VITE_API_BASE_URL as string | undefined) ||
  (typeof window !== 'undefined' ? (window as any).__API_BASE__ : undefined);

const inferDefaultOrigin = () => {
  try {
    // Electron 环境：使用注入的动态端口
    if (typeof window !== 'undefined' && (window as any).__BACKEND_PORT__) {
      const port = (window as any).__BACKEND_PORT__;
      return `http://127.0.0.1:${port}`;
    }

    // Web 环境（开发 dev server 或云服务器）：使用相对路径
    // Vite 代理会自动转发到后端
    if (typeof location !== 'undefined' && location.protocol.startsWith('http')) {
      return '';  // 相对路径
    }
  } catch {}
  return '';  // 默认相对路径
};

// 调试开关（动态检查）
const isDebugApi = () => {
  try {
    return typeof localStorage !== 'undefined' && localStorage.getItem('DEBUG_API') === '1';
  } catch {
    return false;
  }
};

// 导出动态 getter，而非静态常量
export const getApiOrigin = (): string => {
  const backendPort = (window as any).__BACKEND_PORT__;
  const debug = isDebugApi();

  if (debug) {
    console.log('[API] 获取 API Origin - __BACKEND_PORT__:', backendPort, 'RAW_BASE:', RAW_BASE);
  }

  if (RAW_BASE && RAW_BASE.trim().length > 0) {
    if (debug) console.log('[API] 使用 RAW_BASE:', RAW_BASE);
    return RAW_BASE.replace(/\/+$/,'');
  }
  const origin = inferDefaultOrigin();
  if (debug) console.log('[API] 使用推断的 Origin:', origin);
  return origin;
};

export const getApiBaseUrl = (): string => {
  const baseUrl = `${getApiOrigin()}/api/v1`;
  if (isDebugApi()) console.log('[API] API Base URL:', baseUrl);
  return baseUrl;
};

// 兼容旧代码：导出静态常量（初始值）
export const API_ORIGIN = getApiOrigin();
export const API_BASE_URL = getApiBaseUrl();

// 将相对/绝对 URL 规范化为基于 API_ORIGIN 的绝对 URL
export const joinApiUrl = (u: string | URL | null | undefined): string => {
  try {
    const origin = getApiOrigin();
    if (!u) return origin + "/";
    
    const raw = typeof u === 'string' ? u : u.toString();
    
    // 🔧 云服务器兼容：如果是以 / 开头的绝对路径且 origin 为空，直接返回
    // 浏览器会自动基于当前页面 origin 解析
    if (raw.startsWith('/') && (!origin || origin === '')) {
      return raw;
    }
    
    // 若已是完整 URL（http://...），直接返回
    if (raw.startsWith('http://') || raw.startsWith('https://')) {
      return raw;
    }
    
    // 否则拼接 origin
    return new URL(raw, origin.replace(/\/+$/, '/') + '').toString();
  } catch {
    // 兜底：返回原始字符串
    return String(u ?? '');
  }
};

// --- 统一请求封装 ---
export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const p = path.startsWith('/') ? path : `/${path}`;
  const url = `${getApiBaseUrl()}${p}`;
  const res = await fetch(url, { ...(init || {}) });
  if (!res.ok) {
    let msg = '';
    try { msg = await res.text(); } catch {}
    throw new Error(`HTTP ${res.status}${msg ? ' ' + msg : ''}`);
  }
  return res.json() as Promise<T>;
}

export async function postJson<T>(path: string, body?: unknown, init?: RequestInit): Promise<T> {
  return fetchJson<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
    ...init,
  });
}

interface DatasetBrief {
  id: string;
  name: string;
  type: string;
  total_count: number;
  labeled_count: number;
  created_at: string;
  updated_at: string;
}

interface UpdateCaptionRequest {
  caption: string;
}

interface DatasetDetail {
  id: string;
  name: string;
  type: string;
  total_count: number;
  labeled_count: number;
  created_at: string;
  updated_at: string;
  config: Record<string, any>;
  media_items: Array<{
    id: string;
    filename: string;
    file_path: string;
    url: string;
    thumbnail_url: string | null;
    media_type: string;
    caption: string;
    file_size: number;
    dimensions: [number, number] | null;
    created_at: string;
    updated_at: string;
  }>;
  media_total: number;
  media_page: number;
  media_page_size: number;
}

// 数据集相关API
export const datasetApi = {
  // 获取数据集列表
  async listDatasets(page: number = 1, pageSize: number = 50): Promise<{ data: DatasetBrief[]; total: number }> {
    try {
      const response = await fetch(`${getApiBaseUrl()}/datasets?page=${page}&page_size=${pageSize}`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const result = await response.json();
      return {
        data: result.data || [],
        total: result.total || 0
      };
    } catch (error) {
      console.error('获取数据集列表失败:', error);
      throw error;
    }
  },

  // 获取数据集详情
  async getDataset(id: string): Promise<DatasetDetail | null> {
    try {
      const response = await fetch(`${getApiBaseUrl()}/datasets/${id}`);
      if (!response.ok) {
        if (response.status === 404) {
          return null;
        }
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const result = await response.json();
      return result.data || null;
    } catch (error) {
      console.error('获取数据集详情失败:', error);
      throw error;
    }
  },

  // 创建数据集
  async createDataset(data: { name: string; type: string }): Promise<DatasetBrief | null> {
    try {
      const response = await fetch(`${getApiBaseUrl()}/datasets`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      return result.data || null;
    } catch (error) {
      console.error('创建数据集失败:', error);
      throw error;
    }
  },

  // 上传媒体文件到数据集
  async uploadMediaFiles(datasetId: string, files: FileList | File[]): Promise<{ success_count: number; failed_count: number; total_files: number; errors: string[] }> {
    try {
      const formData = new FormData();

      // 将文件添加到FormData中
      Array.from(files).forEach((file) => {
        formData.append('files', file);
      });

      const response = await fetch(`${getApiBaseUrl()}/datasets/${datasetId}/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      return result.data;
    } catch (error) {
      console.error('上传文件失败:', error);
      throw error;
    }
  },

  // 更新媒体文件标注
  async updateMediaCaption(datasetId: string, filename: string, caption: string): Promise<boolean> {
    try {
      const response = await fetch(`${getApiBaseUrl()}/datasets/${datasetId}/media/${encodeURIComponent(filename)}/caption`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ caption }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return true;
    } catch (error) {
      console.error('更新标注失败:', error);
      throw error;
    }
  },

  // 删除媒体文件
  async deleteMediaFile(datasetId: string, filename: string): Promise<boolean> {
    try {
      const response = await fetch(`${getApiBaseUrl()}/datasets/${datasetId}/media/${encodeURIComponent(filename)}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return true;
    } catch (error) {
      console.error('删除文件失败:', error);
      throw error;
    }
  },

  // 删除数据集
  async deleteDataset(id: string): Promise<boolean> {
    try {
      const response = await fetch(`${getApiBaseUrl()}/datasets/${id}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return true;
    } catch (error) {
      console.error('删除数据集失败:', error);
      throw error;
    }
  },

  // 重命名数据集
  async renameDataset(id: string, data: { name: string }): Promise<DatasetDetail | null> {
    try {
      const response = await fetch(`${getApiBaseUrl()}/datasets/${id}/rename`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ new_name: data.name }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      return result.data || null;
    } catch (error) {
      console.error('重命名数据集失败:', error);
      throw error;
    }
  },

  // 获取数据集标签统计
  async getDatasetTagStats(id: string): Promise<Array<{ tag: string; count: number; images: string[] }>> {
    try {
      const response = await fetch(`${getApiBaseUrl()}/datasets/${id}/tags/stats`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const result = await response.json();
      return result.data || [];
    } catch (error) {
      console.error('获取数据集标签统计失败:', error);
      throw error;
    }
  }
};

// 训练任务相关API
export const trainingApi = {
  // 获取训练模型列表
  async getTrainingModels(): Promise<any[]> {
    try {
      const response = await fetch(`${getApiBaseUrl()}/training/models`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const result = await response.json();
      return result.data || [];
    } catch (error) {
      console.error('获取训练模型列表失败:', error);
      throw error;
    }
  },

  // 获取训练配置模式
  async getTrainingConfigSchema(trainingType: string): Promise<any> {
    try {
      const response = await fetch(`${getApiBaseUrl()}/training/config/${trainingType}`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const result = await response.json();
      return result.data || null;
    } catch (error) {
      console.error('获取训练配置模式失败:', error);
      throw error;
    }
  },

  // CLI命令预览
  async previewCliCommand(data: {
    training_type: string;
    config: Record<string, any>;
    dataset_id: string;
    output_dir: string;
  }): Promise<any> {
    try {
      const url = `${getApiBaseUrl()}/training/preview-cli`;
      if (isDebugApi()) console.log('[API] 预览 CLI 请求 URL:', url);
      if (isDebugApi()) console.log('[API] 预览 CLI 请求数据:', data);

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });

      if (isDebugApi()) console.log('[API] 预览 CLI 响应状态:', response.status, response.statusText);

      if (!response.ok) {
        const errorText = await response.text();
        console.error('[API] 预览 CLI 错误响应:', errorText);
        throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
      }
      const result = await response.json();
      if (isDebugApi()) console.log('[API] 预览 CLI 结果:', result);
      return result.data;
    } catch (error) {
      console.error('[API] 生成CLI预览失败:', error);
      throw error;
    }
  },

  // 获取训练任务列表
  async listTasks(): Promise<any[]> {
    try {
      const response = await fetch(`${getApiBaseUrl()}/training/tasks`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const result = await response.json();
      return result.data || [];
    } catch (error) {
      console.error('获取训练任务列表失败:', error);
      return [];
    }
  },

  // 获取训练任务详情
  async getTask(id: string): Promise<any | null> {
    try {
      const response = await fetch(`${getApiBaseUrl()}/training/tasks/${id}`);
      if (!response.ok) {
        if (response.status === 404) {
          return null;
        }
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const result = await response.json();
      return result.data || null;
    } catch (error) {
      console.error('获取训练任务详情失败:', error);
      throw error;
    }
  },

  // 创建训练任务
  async createTask(data: {
    name: string;
    dataset_id: string;
    training_type: string;
    config: Record<string, any>;
  }): Promise<string | null> {
    try {
      const response = await fetch(`${getApiBaseUrl()}/training/tasks`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const result = await response.json();
      return result.data || null;
    } catch (error) {
      console.error('创建训练任务失败:', error);
      throw error;
    }
  },

  // 开始训练任务
  async startTask(id: string): Promise<boolean> {
    try {
      const response = await fetch(`${getApiBaseUrl()}/training/tasks/${id}/start`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return true;
    } catch (error) {
      console.error('开始训练任务失败:', error);
      throw error;
    }
  },

  // 停止训练任务
  async stopTask(id: string): Promise<boolean> {
    try {
      const response = await fetch(`${getApiBaseUrl()}/training/tasks/${id}/stop`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return true;
    } catch (error) {
      console.error('停止训练任务失败:', error);
      throw error;
    }
  },

  // 删除训练任务
  async deleteTask(id: string): Promise<boolean> {
    try {
      const response = await fetch(`${getApiBaseUrl()}/training/tasks/${id}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return true;
    } catch (error) {
      console.error('删除训练任务失败:', error);
      throw error;
    }
  },

  // 刷新任务文件列表
  async refreshTaskFiles(taskId: string): Promise<boolean> {
    try {
      const response = await fetch(`${getApiBaseUrl()}/training/tasks/${taskId}/refresh`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return true;
    } catch (error) {
      console.error('刷新任务文件失败:', error);
      throw error;
    }
  },

  // 获取任务采样图片列表
  async getTaskSamples(taskId: string): Promise<Array<{ filename: string; url: string }>> {
    try {
      const response = await fetch(`${getApiBaseUrl()}/training/tasks/${taskId}/samples`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const result = await response.json();
      return result.items || [];
    } catch (error) {
      console.error('获取采样图片失败:', error);
      return [];
    }
  },

  // 获取任务模型文件列表
  async getTaskArtifacts(taskId: string): Promise<Array<{ filename: string; url: string }>> {
    try {
      const response = await fetch(`${getApiBaseUrl()}/training/tasks/${taskId}/artifacts`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const result = await response.json();
      return result.items || [];
    } catch (error) {
      console.error('获取模型文件失败:', error);
      return [];
    }
  },

  // 获取训练指标数据（Loss和学习率曲线）
  async getTrainingMetrics(taskId: string): Promise<any> {
    try {
      const response = await fetch(`${getApiBaseUrl()}/training/tasks/${taskId}/metrics`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const result = await response.json();
      return result.data || {};
    } catch (error) {
      console.error('获取训练指标失败:', error);
      return {};
    }
  }
};

// 设置相关API
export const settingsApi = {
  // 获取设置
  async getSettings(): Promise<any> {
    try {
      const response = await fetch(`${getApiBaseUrl()}/settings`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const result = await response.json();
      return result.data || {};
    } catch (error) {
      console.error('获取设置失败:', error);
      throw error;
    }
  },

  // 更新设置
  async updateSettings(data: any): Promise<boolean> {
    try {
      const response = await fetch(`${getApiBaseUrl()}/settings`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      return true;
    } catch (error) {
      console.error('更新设置失败:', error);
      throw error;
    }
  }
};

// 打标相关类型定义
export interface LabelingConfigField {
  key: string;
  label: string;
  type: 'text' | 'number' | 'select' | 'file_path' | 'checkbox';
  required: boolean;
  default: any;
  placeholder: string;
  description: string;
  options: Array<{ label: string; value: string }>;
  min?: number;
  max?: number;
  step?: number;
}

export interface LabelingProvider {
  id: string;
  name: string;
  description: string;
  supports_video: boolean;
  is_available: boolean;
  config_fields: LabelingConfigField[];
}

// 打标相关API
export const labelingApi = {
  // 获取所有打标 Provider
  async getProviders(): Promise<LabelingProvider[]> {
    const response = await fetch(`${getApiBaseUrl()}/labeling/providers`);
    if (!response.ok) {
      throw new Error(`获取打标 Provider 失败: ${response.status}`);
    }
    const result = await response.json();
    return result.data as LabelingProvider[];
  },

  // 单张打标
  async labelSingle(datasetId: string, filename: string, prompt?: string): Promise<{ filename: string; caption: string }> {
    const response = await fetch(`${getApiBaseUrl()}/labeling/single`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ dataset_id: datasetId, filename, prompt: prompt || null }),
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    const result = await response.json();
    return result.data as { filename: string; caption: string };
  }
};

// 图片处理相关 API
export const imagesApi = {
  /**
   * 批量裁剪（覆盖原图）。
   * body 示例：
   * {
   *   target_width: 1024,
   *   target_height: 1024,
   *   images: [
   *     { id: "1", source_path: "datasets/image_datasets/xxx/images/a.jpg", transform: { scale: 1.23, offset_x: 10, offset_y: 5 } }
   *   ]
   * }
   */
  async cropBatch(body: {
    target_width: number;
    target_height: number;
    images: Array<{
      id?: string;
      source_path: string;
      transform?: { scale: number; offset_x: number; offset_y: number } | null;
      source_rect?: { x: number; y: number; width: number; height: number } | null;
    }>;
  }): Promise<{ success: boolean; data?: any; message?: string }>
  {
    const res = await fetch(`${getApiBaseUrl()}/images/crop/batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new Error(text || `HTTP ${res.status}`);
    }
    return res.json();
  },

  /**
   * 删除控制图
   */
  async deleteControlImage(
    datasetId: string,
    originalFilename: string,
    controlIndex: number
  ): Promise<void> {
    const url = new URL(`${getApiBaseUrl()}/datasets/${datasetId}/control-images`);
    url.searchParams.append('original_filename', originalFilename);
    url.searchParams.append('control_index', String(controlIndex));

    const res = await fetch(url.toString(), {
      method: 'DELETE',
    });

    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new Error(text || `HTTP ${res.status}`);
    }
  }
};

// GPU监控相关类型定义
interface GPUMetrics {
  id: number;
  name: string;
  memory_total: number;
  memory_used: number;
  memory_free: number;
  memory_utilization: number;
  gpu_utilization: number;
  temperature: number;
  power_draw: number;
  power_limit: number;
  fan_speed?: number;
}

interface SystemGPUResponse {
  gpus: GPUMetrics[];
  timestamp: string;
  total_gpus: number;
}

// 系统监控相关API
export const systemApi = {
  // 获取GPU列表（向后兼容）
  async getGPUs(): Promise<{ data: string[] }> {
    const response = await fetch(`${getApiBaseUrl()}/system/gpus`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return response.json();
  },

  // 获取GPU详细指标
  async getGPUMetrics(): Promise<{ data: SystemGPUResponse }> {
    const response = await fetch(`${getApiBaseUrl()}/system/gpus/metrics`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return response.json();
  },

  // 获取指定GPU的指标
  async getGPUById(gpuId: number): Promise<{ data: GPUMetrics }> {
    const response = await fetch(`${getApiBaseUrl()}/system/gpus/${gpuId}/metrics`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return response.json();
  }
};

// 导出GPU相关类型供其他模块使用
export type { GPUMetrics, SystemGPUResponse };

// 系统就绪状态类型定义
export interface WorkspaceStatus {
  path: string;
  exists: boolean;
  writable: boolean;
  reason: 'NOT_SET' | 'NOT_FOUND' | 'NOT_WRITABLE' | 'OK';
}

export interface RuntimeStatus {
  cwd: string;
  runtime_path: string;
  python_present: boolean;
  engines_present: boolean;
  musubi_present: boolean;
  reason: 'PYTHON_MISSING' | 'MUSUBI_MISSING' | 'ENGINES_MISSING' | 'OK';
}

// 系统就绪状态 API
export const readinessApi = {
  async getWorkspaceStatus(): Promise<{ data: WorkspaceStatus }> {
    const res = await fetch(`${getApiBaseUrl()}/system/workspace/status`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },
  async selectWorkspace(pathStr: string): Promise<{ data: { path: string; ready: boolean; tasks_loaded: boolean; datasets_loaded: boolean; reason: string } }> {
    const res = await fetch(`${getApiBaseUrl()}/system/workspace/select`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: pathStr }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },
  async getRuntimeStatus(): Promise<{ data: RuntimeStatus }> {
    const res = await fetch(`${getApiBaseUrl()}/system/runtime/status`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }
};
