import React, { useState, useEffect } from "react";
import { Card, CardBody, CardHeader, CardFooter, Image, Button, addToast } from "@heroui/react";
import { trainingApi } from "../services/api";

interface ListItem {
  filename: string;
  url: string;
}

interface TaskSamplesViewProps {
  taskId: string;
  refreshSignal?: number; // 由父组件在收到文件变化事件时触发
}

export const TaskSamplesView: React.FC<TaskSamplesViewProps> = ({ taskId, refreshSignal }) => {
  const [samples, setSamples] = useState<ListItem[]>([]);
  const [artifacts, setArtifacts] = useState<ListItem[]>([]);
  const [loading, setLoading] = useState(true);

  // 加载采样结果数据
  const loadData = async () => {
    try {
      setLoading(true);
      const [samplesData, artifactsData] = await Promise.all([
        trainingApi.getTaskSamples(taskId),
        trainingApi.getTaskArtifacts(taskId)
      ]);
      setSamples(samplesData);
      setArtifacts(artifactsData);
    } catch (error) {
      console.error('加载采样结果失败:', error);
    } finally {
      setLoading(false);
    }
  };

  // 文件变化由父组件通过 refreshSignal 触发，这里不直接绑定 WS。

  // 初始加载
  useEffect(() => {
    loadData();
  }, [taskId]);

  // 父层推送的刷新信号（新方式）
  useEffect(() => {
    if (refreshSignal === undefined) return;
    loadData();
  }, [refreshSignal]);

  // 打开系统文件夹
  const openFolder = async (kind: "sample" | "output") => {
    try {
      if (window.electron?.openFolder) {
        const result = await window.electron.openFolder(taskId, kind);
        if (!result.ok) {
          console.error('打开文件夹失败:', result.error);
          // Web环境fallback
          showPathHint(kind);
        }
      } else {
        // Web环境fallback
        showPathHint(kind);
      }
    } catch (error) {
      console.error('打开文件夹出错:', error);
      showPathHint(kind);
    }
  };

  const showPathHint = async (kind: "sample" | "output") => {
    try {
      // 先尝试使用系统默认程序打开文件夹
      const path = `workspace/tasks/${taskId}/output${kind === 'sample' ? '/sample' : ''}`;

      if (window.electron?.shell) {
        const result = await window.electron.shell.showItemInFolder(path);
        if (result.success) {
          return;
        }
      }

      // fallback: 显示路径提示
      addToast({
        title: "文件夹位置",
        description: path,
        color: "primary",
        timeout: 3000
      });
    } catch (error) {
      console.error('打开文件夹失败:', error);
      const path = `workspace/tasks/${taskId}/output${kind === 'sample' ? '/sample' : ''}`;
      addToast({
        title: "文件夹位置",
        description: path,
        color: "primary",
        timeout: 3000
      });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-default-500">加载中...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 过程采样区域 */}
      <Card className="shadow-none" style={{ backgroundColor: 'var(--bg2)' }}>
        <CardHeader className="flex items-center justify-between pb-3">
          <h3 className="text-base font-semibold">过程采样</h3>
          <Button
            size="sm"
            variant="light"
            startContent={<span>📂</span>}
            onPress={() => openFolder("sample")}
            className="text-default-600"
          >
            打开目录
          </Button>
        </CardHeader>
        <CardBody className="pt-0">

          <div className="grid gap-4 grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
            {samples.map((item) => (
              <Card key={item.filename} isFooterBlurred className="border-none aspect-square" radius="lg">
                <Image
                  alt={item.filename}
                  className="object-cover w-full h-full"
                  src={item.url}
                  onError={(e) => {
                    console.error('图片加载失败:', item.url);
                    (e.target as HTMLImageElement).style.display = 'none';
                  }}
                />
                <CardFooter className="justify-center before:bg-white/10 border-white/20 border-1 overflow-hidden py-1 px-2 absolute before:rounded-xl rounded-large bottom-1 w-[calc(100%_-_8px)] shadow-small ml-1 z-10">
                  <p className="text-tiny text-white/80 truncate max-w-full" title={item.filename}>{item.filename}</p>
                </CardFooter>
              </Card>
            ))}
          </div>

          {samples.length === 0 && (
            <div className="text-center py-8 text-default-500">
              <div className="text-4xl mb-2">🎨</div>
              <div>暂无采样图片</div>
              <div className="text-sm text-default-400 mt-1">训练过程中会自动生成</div>
            </div>
          )}
        </CardBody>
      </Card>

      {/* 保存结果区域 */}
      <Card className="shadow-none" style={{ backgroundColor: 'var(--bg2)' }}>
        <CardHeader className="flex items-center justify-between pb-3">
          <h3 className="text-base font-semibold">保存结果</h3>
          <Button
            size="sm"
            variant="light"
            startContent={<span>📂</span>}
            onPress={() => openFolder("output")}
            className="text-default-600"
          >
            打开目录
          </Button>
        </CardHeader>
        <CardBody className="pt-0">

          <div className="grid gap-4 grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
            {artifacts.map((item) => (
              <Card
                key={item.filename}
                className="shadow-none border-none"
                style={{ backgroundColor: 'var(--bg2)' }}
              >
                <CardBody className="p-4 flex flex-col items-center justify-center min-h-[120px]">
                  <div className="w-12 h-12 mb-3 bg-primary-100 rounded-lg flex items-center justify-center text-2xl">
                    📦
                  </div>
                  <span
                    className="text-xs text-default-800 text-center break-all leading-tight"
                    title={item.filename}
                  >
                    {item.filename}
                  </span>
                </CardBody>
              </Card>
            ))}
          </div>

          {artifacts.length === 0 && (
            <div className="text-center py-8 text-default-500">
              <div className="text-4xl mb-2">📦</div>
              <div>暂无模型文件</div>
              <div className="text-sm text-default-400 mt-1">训练完成后会自动生成</div>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
};








