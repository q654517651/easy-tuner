// src/services/api.ts
// 统一 API 基址：优先 VITE_API_BASE，其次按开发环境兜底到 127.0.0.1:8000
const RAW_BASE = (import.meta as any)?.env?.VITE_API_BASE as string | undefined;
const inferDefaultOrigin = () => {
  try {
    if (typeof location !== 'undefined' && location.protocol.startsWith('http')) {
      return `${location.protocol}//127.0.0.1:8000`;
    }
  } catch {}
  return 'http://127.0.0.1:8000';
};
export const API_ORIGIN = (RAW_BASE && RAW_BASE.trim().length > 0)
  ? RAW_BASE.replace(/\/+$/,'')
  : inferDefaultOrigin();
export const API_BASE_URL = `${API_ORIGIN}/api/v1`;

// 将相对/绝对 URL 规范化为基于 API_ORIGIN 的绝对 URL
export const joinApiUrl = (u: string | URL | null | undefined): string => {
  try {
    if (!u) return API_ORIGIN + "/";
    // 若已是 URL 对象或绝对 URL，new URL 会原样返回；相对路径将基于 API_ORIGIN 拼接
    const raw = typeof u === 'string' ? u : u.toString();
    return new URL(raw, API_ORIGIN.replace(/\/+$/, '/') + '').toString();
  } catch {
    // 兜底：返回原始字符串
    return String(u ?? '');
  }
};

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
  description: string;
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
      const response = await fetch(`${API_BASE_URL}/datasets?page=${page}&page_size=${pageSize}`);
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
      const response = await fetch(`${API_BASE_URL}/datasets/${id}`);
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
  async createDataset(data: { name: string; type: string; description?: string }): Promise<DatasetBrief | null> {
    try {
      const response = await fetch(`${API_BASE_URL}/datasets`, {
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

      const response = await fetch(`${API_BASE_URL}/datasets/${datasetId}/upload`, {
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
      const response = await fetch(`${API_BASE_URL}/datasets/${datasetId}/media/${encodeURIComponent(filename)}/caption`, {
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
      const response = await fetch(`${API_BASE_URL}/datasets/${datasetId}/media/${encodeURIComponent(filename)}`, {
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
      const response = await fetch(`${API_BASE_URL}/datasets/${id}`, {
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
      const response = await fetch(`${API_BASE_URL}/datasets/${id}/rename`, {
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
      const response = await fetch(`${API_BASE_URL}/datasets/${id}/tags/stats`);
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
      const response = await fetch(`${API_BASE_URL}/training/models`);
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
      const response = await fetch(`${API_BASE_URL}/training/config/${trainingType}`);
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
      const response = await fetch(`${API_BASE_URL}/training/preview-cli`, {
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
      return result.data;
    } catch (error) {
      console.error('生成CLI预览失败:', error);
      throw error;
    }
  },

  // 获取训练任务列表
  async listTasks(): Promise<any[]> {
    try {
      const response = await fetch(`${API_BASE_URL}/training/tasks`);
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
      const response = await fetch(`${API_BASE_URL}/training/tasks/${id}`);
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
      const response = await fetch(`${API_BASE_URL}/training/tasks`, {
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
      const response = await fetch(`${API_BASE_URL}/training/tasks/${id}/start`, {
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
      const response = await fetch(`${API_BASE_URL}/training/tasks/${id}/stop`, {
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
      const response = await fetch(`${API_BASE_URL}/training/tasks/${id}`, {
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
      const response = await fetch(`${API_BASE_URL}/training/tasks/${taskId}/refresh`, {
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
      const response = await fetch(`${API_BASE_URL}/training/tasks/${taskId}/samples`);
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
      const response = await fetch(`${API_BASE_URL}/training/tasks/${taskId}/artifacts`);
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
      const response = await fetch(`${API_BASE_URL}/training/tasks/${taskId}/metrics`);
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
      const response = await fetch(`${API_BASE_URL}/settings`);
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
      const response = await fetch(`${API_BASE_URL}/settings`, {
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

// 打标相关API
export const labelingApi = {
  // 单张打标
  async labelSingle(datasetId: string, filename: string, prompt?: string): Promise<{ filename: string; caption: string }> {
    const response = await fetch(`${API_BASE_URL}/labeling/single`, {
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
    const response = await fetch(`${API_BASE_URL}/system/gpus`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return response.json();
  },

  // 获取GPU详细指标
  async getGPUMetrics(): Promise<{ data: SystemGPUResponse }> {
    const response = await fetch(`${API_BASE_URL}/system/gpus/metrics`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return response.json();
  },

  // 获取指定GPU的指标
  async getGPUById(gpuId: number): Promise<{ data: GPUMetrics }> {
    const response = await fetch(`${API_BASE_URL}/system/gpus/${gpuId}/metrics`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return response.json();
  }
};

// 导出GPU相关类型供其他模块使用
export type { GPUMetrics, SystemGPUResponse };

// 系统就绪状态 API
export const readinessApi = {
  async getWorkspaceStatus(): Promise<{ data: { path: string; exists: boolean; writable: boolean } }> {
    const res = await fetch(`${API_BASE_URL}/system/workspace/status`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },
  async selectWorkspace(pathStr: string): Promise<{ data: { path: string } }> {
    const res = await fetch(`${API_BASE_URL}/system/workspace/select`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: pathStr }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },
  async getRuntimeStatus(): Promise<{ data: { cwd: string; runtime_path: string; python_present: boolean; engines_present: boolean } }> {
    const res = await fetch(`${API_BASE_URL}/system/runtime/status`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }
};
