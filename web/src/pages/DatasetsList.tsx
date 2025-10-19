import { addToast, Button, Alert } from "@heroui/react";
import CreateDatasetDialog from "../ui/CreateDatasetDialog";
import { useEffect, useState } from "react";
import { datasetApi } from "../services/api";
import EmptyState from "../ui/EmptyState";
import EmptyImg from "../assets/img/EmptyDataset.png?inline";
import DatasetRow from "../ui/DatasetRow";
import { useReadiness } from "../contexts/ReadinessContext";
import { useNavigate } from "react-router-dom";
import WorkspaceSelectModal from "../components/WorkspaceSelectModal";
import { PageLayout } from "../layouts/PageLayout";

interface Dataset {
  id: string;
  name: string;
  type: string;
  total_count: number;
  labeled_count: number;
  created_at: string;
  updated_at: string;
}

export default function DatasetsList() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const { workspaceReady } = useReadiness();
  const navigate = useNavigate();
  const [showWorkspaceModal, setShowWorkspaceModal] = useState(false);

  useEffect(() => {
    const fetchDatasets = async () => {
      try {
        setLoading(true);
        const { data } = await datasetApi.listDatasets();
        setDatasets(data);
        setError(null);
      } catch (err) {
        console.error('获取数据集列表失败:', err);
        setError('获取数据集列表失败');
      } finally {
        setLoading(false);
      }
    };

    fetchDatasets();
  }, []);

  const handleCreateDataset = async (data: { name: string; type: string; description: string }) => {
    try {
      const newDataset = await datasetApi.createDataset(data);
      if (newDataset) {
        // 刷新数据集列表
        const { data: updatedDatasets } = await datasetApi.listDatasets();
        setDatasets(updatedDatasets);

        // 显示成功通知
        addToast({
          title: "创建成功",
          description: `数据集"${data.name}"已创建完成`,
          color: "success",
          timeout: 3000
        });
      }
    } catch (error) {
      console.error('创建数据集失败:', error);

      // 显示失败通知
      const errorMessage = error instanceof Error ? error.message : '创建失败';
      addToast({
        title: "创建失败",
        description: errorMessage,
        color: "danger",
        timeout: 3000
      });

      throw error;
    }
  };

  const refreshDatasets = async () => {
    const { data: updated } = await datasetApi.listDatasets();
    setDatasets(updated);
  };

  const handleRename = async (id: string, newName: string) => {
    try {
      await datasetApi.renameDataset(id, { name: newName });
      await refreshDatasets();
    } catch (err) {
      console.error("重命名失败:", err);
      throw err; // 让Row组件的handleRenameSubmit处理错误显示
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await datasetApi.deleteDataset(id);
      await refreshDatasets();
    } catch (err) {
      console.error("删除失败:", err);
      throw err; // 让Row组件的handleConfirmDelete处理错误显示
    }
  };

  const handleCreateButtonClick = () => {
    if (!workspaceReady) {
      setShowWorkspaceModal(true);
    } else {
      setShowCreateDialog(true);
    }
  };

  if (loading) {
    return (
      <PageLayout
        crumbs={[{ label: "数据集" }]}
        actions={
          <Button
            onClick={() => setShowCreateDialog(true)}
            variant="bordered"
            size="sm"
            startContent="✨"
          >
            创建数据集
          </Button>
        }
      >
        <div className="p-6">加载中...</div>
      </PageLayout>
    );
  }

  if (error) {
    return (
      <PageLayout
        crumbs={[{ label: "数据集" }]}
        actions={
          <Button
            onClick={() => setShowCreateDialog(true)}
            variant="bordered"
            size="sm"
            startContent="✨"
          >
            创建数据集
          </Button>
        }
      >
        <div className="p-6 text-red-500">错误: {error}</div>
      </PageLayout>
    );
  }

  return (
    <PageLayout
      crumbs={[{ label: "数据集" }]}
      actions={
        <Button
          onClick={handleCreateButtonClick}
          variant="bordered"
          size="sm"
          startContent="✨"
        >
          创建数据集
        </Button>
      }
    >
      <div className="flex flex-col h-full">
          {!workspaceReady && (
            <div className="p-6 pb-0">
              <Alert
                color="warning"
                title="工作区未设置"
                description="创建数据集前需要先设置工作区目录"
                endContent={
                  <Button
                    size="sm"
                    variant="flat"
                    color="warning"
                    onClick={() => setShowWorkspaceModal(true)}
                  >
                    设置工作区
                  </Button>
                }
              />
            </div>
          )}
          {datasets.length === 0 ? (
            <div className="flex-1 flex items-center justify-center">
              <EmptyState image={EmptyImg} message="暂无数据集，先去创建一个吧" />
            </div>
          ) : (
            <div className="p-6 space-y-4">
              {datasets.map((dataset) => (
                <DatasetRow key={dataset.id} {...dataset} onRename={handleRename} onDelete={handleDelete} />
              ))}
            </div>
          )}
      </div>

      {/* 创建数据集对话框 */}
      <CreateDatasetDialog
        isOpen={showCreateDialog}
        onClose={() => setShowCreateDialog(false)}
        onSubmit={handleCreateDataset}
      />

      {/* 工作区选择对话框 */}
      <WorkspaceSelectModal
        isOpen={showWorkspaceModal}
        onClose={() => setShowWorkspaceModal(false)}
        onSuccess={refreshDatasets}
      />
    </PageLayout>
  );
}
