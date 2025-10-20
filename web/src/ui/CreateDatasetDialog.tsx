import { useState, useEffect } from 'react';
import { Modal, ModalContent, ModalHeader, ModalBody, ModalFooter, Button, Input, Select, SelectItem } from '@heroui/react';
import { fetchJson } from '../services/api';
import { useReadiness } from '../contexts/ReadinessContext';
import { readinessApi } from '../services/api';

interface CreateDatasetDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: { name: string; type: string }) => Promise<void>;
}

export default function CreateDatasetDialog({ isOpen, onClose, onSubmit }: CreateDatasetDialogProps) {
  const [name, setName] = useState('');
  const [type, setType] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [datasetTypes, setDatasetTypes] = useState<{value: string; label: string}[]>([]);

  useEffect(() => {
    const fetchDatasetTypes = async () => {
      try {
        const result = await fetchJson<any>('/datasets/types');
        if (result.success && result.data) {
          setDatasetTypes(result.data);
          // 设置默认选中第一个类型
          if (result.data.length > 0 && !type) {
            setType(result.data[0].value);
          }
        }
      } catch (error) {
        console.error('Error fetching dataset types:', error);
      }
    };

    fetchDatasetTypes();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!name.trim()) {
      setError('数据集名称不能为空');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      await onSubmit({ name: name.trim(), type });
      // 重置表单
      setName('');
      setType(datasetTypes.length > 0 ? datasetTypes[0].value : '');
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建失败');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      setName('');
      setType(datasetTypes.length > 0 ? datasetTypes[0].value : '');
      setError(null);
      onClose();
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      isDismissable={!loading}
      isKeyboardDismissDisabled={loading}
      placement="center"
      size="md"
    >
      <ModalContent>
        <form onSubmit={handleSubmit}>
          <ModalHeader className="flex flex-col gap-1">
            创建数据集
          </ModalHeader>
          <ModalBody>
            <div className="flex flex-col gap-4">
              {/* 数据集名称 */}
              <Input
                label="数据集名称"
                placeholder="请输入数据集名称"
                value={name}
                onValueChange={setName}
                isRequired
                isDisabled={loading}
                variant="bordered"
                labelPlacement="outside"
                isInvalid={!!error && !name.trim()}
                errorMessage={error && !name.trim() ? "数据集名称不能为空" : ""}
              />

              {/* 数据集类型 */}
              <Select
                label="数据集类型"
                placeholder="选择数据集类型"
                selectedKeys={type ? [type] : []}
                onSelectionChange={(keys) => setType(Array.from(keys)[0] as string)}
                isDisabled={loading}
                variant="bordered"
                labelPlacement="outside"
              >
                {datasetTypes.map((datasetType) => (
                  <SelectItem key={datasetType.value} value={datasetType.value}>
                    {datasetType.label}
                  </SelectItem>
                ))}
              </Select>

              {/* 错误信息 */}
              {error && (
                <div className="text-danger text-small">
                  {error}
                </div>
              )}
            </div>
          </ModalBody>
          <ModalFooter>
            <Button
              color="default"
              variant="bordered"
              onPress={handleClose}
              isDisabled={loading}
            >
              取消
            </Button>
            <Button
              color="primary"
              type="submit"
              isDisabled={loading || !name.trim()}
              isLoading={loading}
            >
              {loading ? '创建中...' : '创建'}
            </Button>
          </ModalFooter>
        </form>
      </ModalContent>
    </Modal>
  );
}
