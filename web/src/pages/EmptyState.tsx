import React from "react";
import { useParams } from "react-router-dom";
import HeaderBar from "../ui/HeaderBar";
import EmptyState from "../ui/EmptyState";
import EmptyDatasetImg from "../assets/img/EmptyDataset.png?inline";

// kind 可选：datasets | dataset-images | tasks
const messages: Record<string, string> = {
  datasets: "暂无数据集，先去创建一个吧",
  "dataset-images": "这个数据集还没有图片，拖拽或上传一些吧",
  tasks: "暂无训练任务，先创建一个训练吧",
};

export default function EmptyStatePage() {
  const { kind } = useParams<{ kind?: string }>();
  const k = kind && messages[kind] ? kind : "datasets";
  const message = messages[k];

  return (
    <div className="flex flex-col h-full">
      <HeaderBar crumbs={[{ label: "空状态" }, { label: message }]} />
      <div className="flex-1">
        <EmptyState image={EmptyDatasetImg} message={message} />
      </div>
    </div>
  );
}
