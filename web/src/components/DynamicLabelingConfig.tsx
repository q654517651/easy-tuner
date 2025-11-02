import React, { useState, useEffect } from 'react';
import GroupCard from '../ui/GroupCard';
import { HeroInput, HeroSelect, HeroTextarea } from '../ui/HeroFormControls';
import { labelingApi, type LabelingProvider, type LabelingConfigField } from '../services/api';

interface DynamicLabelingConfigProps {
  settings: any;
  onUpdate: (settings: any) => void;
}

export default function DynamicLabelingConfig({ settings, onUpdate }: DynamicLabelingConfigProps) {
  const [providers, setProviders] = useState<LabelingProvider[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadProviders();
  }, []);

  const loadProviders = async () => {
    try {
      const data = await labelingApi.getProviders();
      setProviders(data);
    } catch (error) {
      console.error('加载打标 Provider 失败:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  const selectedProviderId = settings.labeling.selected_model;
  const selectedProvider = providers.find(p => p.id === selectedProviderId);

  // 渲染单个配置字段
  const renderField = (field: LabelingConfigField) => {
    const value = settings.labeling.models[selectedProviderId]?.[field.key] ?? field.default;

    const handleChange = (newValue: any) => {
      onUpdate({
        ...settings,
        labeling: {
          ...settings.labeling,
          models: {
            ...settings.labeling.models,
            [selectedProviderId]: {
              ...(settings.labeling.models[selectedProviderId] || {}),
              [field.key]: newValue
            }
          }
        }
      });
    };

    switch (field.type) {
      case 'text':
      case 'file_path':
        return (
          <HeroInput
            key={field.key}
            label={field.label}
            value={value || ''}
            placeholder={field.placeholder}
            onChange={handleChange}
            help={field.description}
          />
        );

      case 'number':
        return (
          <HeroInput
            key={field.key}
            label={field.label}
            type="number"
            value={value ?? field.default}
            min={field.min}
            max={field.max}
            step={field.step}
            onChange={(v) => handleChange(Number(v))}
            help={field.description}
          />
        );

      case 'select':
        return (
          <HeroSelect
            key={field.key}
            label={field.label}
            value={value || field.default}
            options={field.options}
            onChange={handleChange}
            help={field.description}
          />
        );

      case 'checkbox':
        return (
          <div key={field.key} className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={!!value}
              onChange={(e) => handleChange(e.target.checked)}
              className="rounded border-gray-300"
            />
            <label className="text-sm">{field.label}</label>
            {field.description && (
              <span className="text-xs text-gray-500">({field.description})</span>
            )}
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <>
      <GroupCard title="基本设置">
        <HeroSelect
          label="选择打标模型"
          value={selectedProviderId}
          options={providers.map(p => ({
            label: p.name,
            value: p.id
          }))}
          onChange={(value) =>
            onUpdate({
              ...settings,
              labeling: { ...settings.labeling, selected_model: value }
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
            onUpdate({
              ...settings,
              labeling: {
                ...settings.labeling,
                delay_between_calls: Number(value) || 0
              }
            })
          }
        />
        <div className="md:col-span-2">
          <HeroTextarea
            label="默认打标提示词"
            value={settings.labeling.default_prompt}
            rows={4}
            onChange={(value) =>
              onUpdate({
                ...settings,
                labeling: { ...settings.labeling, default_prompt: String(value) }
              })
            }
          />
        </div>
      </GroupCard>

      {selectedProvider && (
        <GroupCard title={`${selectedProvider.name} 配置`}>
          {selectedProvider.config_fields.map(field => renderField(field))}
        </GroupCard>
      )}
    </>
  );
}
