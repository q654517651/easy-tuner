/**
 * Model Weight Grouping Utilities
 *
 * Automatically groups training models by type_name and separates
 * shared weights (vae, text_encoder, clip) from unique weights (dit, unet)
 */

export interface ModelField {
  key: string;
  label: string;
  help: string;
  setting_path: string;
}

export interface ModelGroup {
  title: string;
  fields: ModelField[];
}

export interface ModelPathsSchema {
  [modelType: string]: ModelGroup;
}

export interface GroupedModel {
  groupKey: string;
  groupTitle: string;
  models: {
    typeName: string;
    title: string;
    allFields: ModelField[];  // 所有字段，不再区分 shared/unique
  }[];
}

/**
 * Determines which group a model belongs to based on its type_name
 *
 * 规则：使用下划线前面的部分作为分组键
 * - qwen_image → qwen
 * - qwen_image_edit → qwen
 * - flux_kontext → flux
 * - Wan_2.1 → wan
 * - Wan_2.2 → wan
 */
export function getModelGroupKey(typeName: string): string {
  const lower = typeName.toLowerCase();

  // 按下划线分割，取第一部分作为分组键
  const parts = lower.split('_');
  if (parts.length > 0 && parts[0]) {
    return parts[0];
  }

  // 如果没有下划线，直接返回小写形式
  return lower;
}

/**
 * 判断字段是否应该占满整行（dit/unet 占一行，其他占半行）
 */
export function isFullWidthField(fieldKey: string): boolean {
  return fieldKey === 'dit_path' || fieldKey === 'unet_path';
}

/**
 * 判断是否为共享权重字段
 */
export function isSharedField(fieldKey: string): boolean {
  const sharedFieldPatterns = [
    'vae_path',
    'text_encoder_path',
    'text_encoder1_path',
    'text_encoder2_path',
    'clip_path',
    't5_path'
  ];

  return sharedFieldPatterns.includes(fieldKey);
}

/**
 * Groups models by their group key
 */
export function buildModelGroups(schema: ModelPathsSchema): GroupedModel[] {
  const groupsMap: Map<string, GroupedModel> = new Map();

  // Process each model in the schema
  for (const [typeName, modelGroup] of Object.entries(schema)) {
    const groupKey = getModelGroupKey(typeName);

    // Get or create group
    if (!groupsMap.has(groupKey)) {
      groupsMap.set(groupKey, {
        groupKey,
        groupTitle: modelGroup.title.split(' ')[0], // e.g., "Qwen-Image 模型" → "Qwen-Image"
        models: []
      });
    }

    const group = groupsMap.get(groupKey)!;
    group.models.push({
      typeName,
      title: modelGroup.title,
      allFields: modelGroup.fields
    });
  }

  return Array.from(groupsMap.values());
}

/**
 * 从配置读取字段值
 * 对于共享字段（如vae_path），从该组第一个模型读取
 * 对于独占字段（如dit_path），从指定模型读取
 */
export function getGroupedValue(
  settings: any,
  groupKey: string,
  typeName: string,
  fieldKey: string,
  settingPath: string
): string {
  // 直接使用 settingPath 读取值
  const keys = settingPath.split('.');
  let value = settings;
  for (const key of keys) {
    if (value && typeof value === 'object' && key in value) {
      value = value[key];
    } else {
      return '';
    }
  }

  return typeof value === 'string' ? value : '';
}

/**
 * 更新配置字段值
 * 对于共享字段（如vae_path），同时更新该组所有模型
 * 对于独占字段（如dit_path），仅更新指定模型
 */
export function setGroupedValue(
  settings: any,
  groupKey: string,
  typeName: string,
  fieldKey: string,
  settingPath: string,
  value: string,
  allModelsInGroup: Array<{typeName: string, allFields: ModelField[]}>
): any {
  const newSettings = JSON.parse(JSON.stringify(settings)); // Deep clone

  if (isSharedField(fieldKey)) {
    // 共享字段：更新该组所有模型
    // 从每个模型的字段中找到对应的 setting_path
    for (const model of allModelsInGroup) {
      const field = model.allFields.find(f => f.key === fieldKey);
      if (!field) continue;

      const modelPath = field.setting_path;  // 使用 setting_path 而不是拼接 typeName
      const keys = modelPath.split('.');
      let current = newSettings;

      for (let i = 0; i < keys.length - 1; i++) {
        const key = keys[i];
        if (!current[key]) {
          current[key] = {};
        }
        current = current[key];
      }

      current[keys[keys.length - 1]] = value;
    }
  } else {
    // 独占字段（dit_path）：仅更新当前模型
    const keys = settingPath.split('.');
    let current = newSettings;

    for (let i = 0; i < keys.length - 1; i++) {
      const key = keys[i];
      if (!current[key]) {
        current[key] = {};
      }
      current = current[key];
    }

    current[keys[keys.length - 1]] = value;
  }

  return newSettings;
}

/**
 * Gets a user-friendly group title
 */
export function getGroupDisplayTitle(groupKey: string): string {
  const titleMap: { [key: string]: string } = {
    'qwen': 'Qwen 系列',
    'flux': 'Flux 系列',
    'wan': 'Wan 系列',
    'stable': 'Stable Diffusion 系列'
  };

  return titleMap[groupKey] || groupKey.toUpperCase();
}
