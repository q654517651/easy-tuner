import React, { useState } from "react";
import HeaderBar from "../ui/HeaderBar";
import AppButton from "../ui/primitives/Button";
import { HeroInput, HeroSelect, HeroSwitch, HeroTextarea } from "../ui/HeroFormControls";
import { AppModal, ConfirmModal } from "../ui/primitives/Modal";
import DatasetRow from "../ui/DatasetRow";
import TaskRow from "../ui/TaskRow";
import { DatasetCard } from "../ui/dataset-card";
import { CropCard } from "../ui/dataset-card/CropCard";

export default function UITest() {
  const [textValue, setTextValue] = useState("");
  const [numberValue, setNumberValue] = useState<number | "">(0);
  const [selectValue, setSelectValue] = useState("option1");
  const [switchValue, setSwitchValue] = useState(false);
  const [textareaValue, setTextareaValue] = useState("");
  const [basicModalOpen, setBasicModalOpen] = useState(false);
  const [confirmModalOpen, setConfirmModalOpen] = useState(false);
  const [formModalOpen, setFormModalOpen] = useState(false);
  const [blockingModalOpen, setBlockingModalOpen] = useState(false);
  const [renameModalOpen, setRenameModalOpen] = useState(false);
  const [formName, setFormName] = useState("");
  const [formType, setFormType] = useState("image");
  const [renameName, setRenameName] = useState("");

  // 裁剪卡片测试状态
  const [cropTargetWidth, setCropTargetWidth] = useState(512);
  const [cropTargetHeight, setCropTargetHeight] = useState(768);

  return (
    <div className="flex flex-col h-full">
      <HeaderBar
        crumbs={[{ label: "UI 测试" }]}
        actions={
          <AppButton kind="outlined" startIcon={<span>🧪</span>}>
            测试按钮
          </AppButton>
        }
      />

      <div className="flex-1 overflow-y-auto p-6 space-y-8">
        <section>
          <h3 className="text-sm font-semibold opacity-70 mb-3">Filled（填充）</h3>
          <div className="flex flex-wrap gap-3">
            <AppButton color="primary">Primary</AppButton>
            <AppButton color="success">Success</AppButton>
            <AppButton color="danger">Danger</AppButton>
            <AppButton color="default">Default</AppButton>
            <AppButton color="primary" startIcon={<span>✨</span>}>
              带图标
            </AppButton>
          </div>
        </section>

        <section>
          <h3 className="text-sm font-semibold opacity-70 mb-3">Outlined（描边）</h3>
          <div className="flex flex-wrap gap-3">
            <AppButton kind="outlined" color="primary">
              Primary
            </AppButton>
            <AppButton kind="outlined" color="success">
              Success
            </AppButton>
            <AppButton kind="outlined" color="danger">
              Danger
            </AppButton>
            <AppButton kind="outlined" color="default">
              Default
            </AppButton>
            <AppButton kind="outlined" color="primary" startIcon={<span>✨</span>}>
              带图标
            </AppButton>
          </div>
        </section>

        <section>
          <h3 className="text-sm font-semibold opacity-70 mb-3">表单控件</h3>
          <div className="space-y-4 max-w-md">
            <HeroInput
              label="文本输入"
              value={textValue}
              onChange={setTextValue}
              placeholder="请输入文本"
            />
            <HeroInput
              label="数字输入"
              type="number"
              value={numberValue}
              onChange={setNumberValue}
              placeholder="请输入数字"
            />
            <HeroSelect
              label="下拉选择"
              value={selectValue}
              options={[
                { label: "选项一", value: "option1" },
                { label: "选项二", value: "option2" },
                { label: "选项三", value: "option3" },
              ]}
              onChange={setSelectValue}
            />
            <HeroSwitch
              label="开关控件"
              checked={switchValue}
              onChange={setSwitchValue}
              description="这是一个开关说明"
            />
            <HeroTextarea
              label="多行文本"
              value={textareaValue}
              onChange={setTextareaValue}
              placeholder="请输入多行文本"
              rows={3}
            />
          </div>
        </section>

        <section>
          <h3 className="text-sm font-semibold opacity-70 mb-3">模态框</h3>
          <div className="flex flex-wrap gap-3">
            <AppButton color="primary" onClick={() => setBasicModalOpen(true)}>
              基础模态框
            </AppButton>
            <AppButton color="danger" onClick={() => setConfirmModalOpen(true)}>
              确认对话框
            </AppButton>
            <AppButton color="success" onClick={() => setFormModalOpen(true)}>
              表单模态框
            </AppButton>
            <AppButton color="default" onClick={() => setBlockingModalOpen(true)}>
              阻断式模态框
            </AppButton>
            <AppButton kind="outlined" color="primary" onClick={() => setRenameModalOpen(true)}>
              重命名模态框
            </AppButton>
          </div>
        </section>

        <section>
          <h3 className="text-sm font-semibold opacity-70 mb-3">列表 Row</h3>
          <div className="space-y-3">
            <DatasetRow
              id="demo-dataset-1"
              name="图片数据集示例"
              type="image"
              total_count={120}
              labeled_count={85}
              onRename={(id, newName) => alert(`重命名数据集 ${id} 为 ${newName}`)}
              onDelete={(id) => alert(`删除数据集 ${id}`)}
            />
            <DatasetRow
              id="demo-dataset-2"
              name="视频数据集示例"
              type="video"
              total_count={45}
              labeled_count={30}
              onRename={(id, newName) => alert(`重命名数据集 ${id} 为 ${newName}`)}
              onDelete={(id) => alert(`删除数据集 ${id}`)}
            />
            <DatasetRow
              id="demo-dataset-3"
              name="控制图数据集示例"
              type="image_control"
              total_count={200}
              labeled_count={150}
              onRename={(id, newName) => alert(`重命名数据集 ${id} 为 ${newName}`)}
              onDelete={(id) => alert(`删除数据集 ${id}`)}
            />
            <TaskRow
              task={{
                id: "demo-task-1",
                name: "示例训练任务",
                status: "running",
                done: 450,
                total: 1000,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
              }}
              onTaskDeleted={() => alert("任务已删除")}
            />
          </div>
        </section>

        <section>
          <h3 className="text-sm font-semibold opacity-70 mb-3">数据集卡片</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* 图片卡片 */}
            <DatasetCard
              mediaType="image"
              url="https://picsum.photos/seed/demo1/800/600"
              filename="sample-image.jpg"
              caption="这是一张示例图片的标注文本"
              selected={false}
              onSelect={(selected) => console.log("Image selected:", selected)}
              onDelete={() => alert("删除图片卡片")}
              onCaptionSave={(caption) => console.log("保存标注:", caption)}
              onAutoLabel={() => alert("自动打标")}
            />

            {/* 视频卡片 */}
            <DatasetCard
              mediaType="video"
              url="https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
              filename="sample-video.mp4"
              caption="这是一个示例视频的标注文本"
              selected={false}
              onSelect={(selected) => console.log("Video selected:", selected)}
              onDelete={() => alert("删除视频卡片")}
              onCaptionSave={(caption) => console.log("保存标注:", caption)}
            />

            {/* 单图控制卡片（需要上传） */}
            <DatasetCard
              mediaType="single_control_image"
              url="https://picsum.photos/seed/upload1/800/600"
              filename="need-upload.jpg"
              caption="需要上传控制图的示例"
              controlImages={[]}
              selected={false}
              onSelect={(selected) => console.log("Upload needed selected:", selected)}
              onDelete={() => alert("删除卡片")}
              onCaptionSave={(caption) => console.log("保存标注:", caption)}
              onUploadControl={(slotIndex) => alert(`上传控制图到位置 ${slotIndex}`)}
              onDeleteControl={(slotIndex) => alert(`删除控制图位置 ${slotIndex}`)}
            />

            {/* 单图控制卡片（已有控制图） */}
            <DatasetCard
              mediaType="single_control_image"
              url="https://picsum.photos/seed/demo2/800/600"
              filename="single-control-image.jpg"
              caption="这是一个单图控制的标注文本"
              controlImages={[
                { url: "https://picsum.photos/seed/control1/400/300", filename: "control1.jpg" }
              ]}
              selected={false}
              onSelect={(selected) => console.log("Single control image selected:", selected)}
              onDelete={() => alert("删除单图控制卡片")}
              onCaptionSave={(caption) => console.log("保存标注:", caption)}
              onUploadControl={(slotIndex) => alert(`上传控制图到位置 ${slotIndex}`)}
              onDeleteControl={(slotIndex) => alert(`删除控制图位置 ${slotIndex}`)}
            />

            {/* 多图控制卡片 */}
            <DatasetCard
              mediaType="multi_control_image"
              url="https://picsum.photos/seed/demo3/800/600"
              filename="multi-control-image.jpg"
              caption="这是一个多图控制的标注文本，支持最多3张控制图"
              controlImages={[
                { url: "https://picsum.photos/seed/control1/400/300", filename: "control1.jpg" },
                { url: "https://picsum.photos/seed/control2/400/300", filename: "control2.jpg" },
                { url: "https://picsum.photos/seed/control3/400/300", filename: "control3.jpg" }
              ]}
              selected={false}
              onSelect={(selected) => console.log("Multi control image selected:", selected)}
              onDelete={() => alert("删除多图控制卡片")}
              onCaptionSave={(caption) => console.log("保存标注:", caption)}
              onUploadControl={(slotIndex) => alert(`上传控制图到位置 ${slotIndex}`)}
              onDeleteControl={(slotIndex) => alert(`删除控制图位置 ${slotIndex}`)}
            />
          </div>
        </section>

        <section>
          <h3 className="text-sm font-semibold opacity-70 mb-3">图片裁剪卡片</h3>

          {/* 控制面板 */}
          <div className="mb-4 p-4 bg-content2 dark:bg-content2 rounded-lg">
            <div className="flex items-center gap-4">
              <label className="text-sm font-medium">目标尺寸：</label>
              <HeroInput
                type="number"
                value={cropTargetWidth}
                onChange={(e) => setCropTargetWidth(Math.max(1, parseInt(e.target.value) || 1))}
                placeholder="宽度"
                style={{ width: '120px' }}
              />
              <span className="text-sm">×</span>
              <HeroInput
                type="number"
                value={cropTargetHeight}
                onChange={(e) => setCropTargetHeight(Math.max(1, parseInt(e.target.value) || 1))}
                placeholder="高度"
                style={{ width: '120px' }}
              />
              <span className="text-sm text-default-600">
                ({cropTargetWidth}:{cropTargetHeight} ≈ {(cropTargetWidth / cropTargetHeight).toFixed(2)})
              </span>
            </div>
          </div>

          {/* 裁剪卡片示例 */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* 横图示例 */}
            <CropCard
              url="https://picsum.photos/seed/wide1/1920/1080"
              filename="wide-image.jpg"
              targetWidth={cropTargetWidth}
              targetHeight={cropTargetHeight}
              onCropChange={(params) => {
                console.log('横图裁剪参数:', params);
              }}
            />

            {/* 竖图示例 */}
            <CropCard
              url="https://picsum.photos/seed/tall1/1080/1920"
              filename="tall-image.jpg"
              targetWidth={cropTargetWidth}
              targetHeight={cropTargetHeight}
              onCropChange={(params) => {
                console.log('竖图裁剪参数:', params);
              }}
            />

            {/* 方图示例 */}
            <CropCard
              url="https://picsum.photos/seed/square1/1080/1080"
              filename="square-image.jpg"
              targetWidth={cropTargetWidth}
              targetHeight={cropTargetHeight}
              onCropChange={(params) => {
                console.log('方图裁剪参数:', params);
              }}
            />
          </div>
        </section>
      </div>

      {/* 基础模态框 */}
      <AppModal
        isOpen={basicModalOpen}
        onClose={() => setBasicModalOpen(false)}
        title="基础模态框"
        footer={
          <AppButton color="primary" onClick={() => setBasicModalOpen(false)}>
            关闭
          </AppButton>
        }
      >
        <p>这是一个基础的模态框示例，可以放置任何内容。</p>
        <p className="mt-2 text-sm opacity-70">支持自定义标题、内容和底部按钮。</p>
      </AppModal>

      {/* 确认对话框 */}
      <ConfirmModal
        isOpen={confirmModalOpen}
        onClose={() => setConfirmModalOpen(false)}
        onConfirm={() => {
          alert("已确认！");
          setConfirmModalOpen(false);
        }}
        title="确认操作"
        confirmText="确认"
        cancelText="取消"
        confirmColor="danger"
      >
        <p>确定要执行此操作吗？此操作不可撤销。</p>
      </ConfirmModal>

      {/* 表单模态框（模拟创建数据集） */}
      <AppModal
        isOpen={formModalOpen}
        onClose={() => {
          setFormModalOpen(false);
          setFormName("");
          setFormType("image");
        }}
        title="创建数据集"
        footer={
          <div className="flex gap-2">
            <AppButton
              kind="outlined"
              color="default"
              onClick={() => {
                setFormModalOpen(false);
                setFormName("");
                setFormType("image");
              }}
            >
              取消
            </AppButton>
            <AppButton
              color="primary"
              onClick={() => {
                alert(`创建数据集：${formName}，类型：${formType}`);
                setFormModalOpen(false);
                setFormName("");
                setFormType("image");
              }}
              disabled={!formName.trim()}
            >
              创建
            </AppButton>
          </div>
        }
      >
        <div className="space-y-4">
          <HeroInput
            label="数据集名称"
            value={formName}
            onChange={setFormName}
            placeholder="请输入数据集名称"
            isRequired
            labelPlacement="outside-top"
          />
          <HeroSelect
            label="数据集类型"
            value={formType}
            options={[
              { label: "图片数据集", value: "image" },
              { label: "视频数据集", value: "video" },
              { label: "控制图数据集", value: "image_control" },
            ]}
            onChange={setFormType}
            labelPlacement="outside-top"
          />
        </div>
      </AppModal>

      {/* 阻断式模态框（不可关闭，模拟工作区选择） */}
      <AppModal
        isOpen={blockingModalOpen}
        onClose={() => {}}
        title="选择工作区"
        hideCloseButton={true}
        isDismissable={false}
        footer={
          <AppButton
            color="primary"
            onClick={() => {
              alert("工作区已设置");
              setBlockingModalOpen(false);
            }}
          >
            确定
          </AppButton>
        }
      >
        <div className="space-y-4">
          <p>首次使用需指定工作区目录，用于存放任务、数据集与日志。</p>
          <div className="flex gap-2">
            <HeroInput
              label="工作区路径"
              value="/path/to/workspace"
              onChange={() => {}}
              placeholder="未选择"
              className="flex-1"
              labelPlacement="outside-top"
            />
            <AppButton color="default" className="mt-6">
              浏览...
            </AppButton>
          </div>
        </div>
      </AppModal>

      {/* 重命名模态框 */}
      <AppModal
        isOpen={renameModalOpen}
        onClose={() => {
          setRenameModalOpen(false);
          setRenameName("");
        }}
        title="重命名数据集"
        footer={
          <div className="flex gap-2">
            <AppButton
              kind="outlined"
              color="default"
              onClick={() => {
                setRenameModalOpen(false);
                setRenameName("");
              }}
            >
              取消
            </AppButton>
            <AppButton
              color="primary"
              onClick={() => {
                alert(`重命名为：${renameName}`);
                setRenameModalOpen(false);
                setRenameName("");
              }}
              disabled={!renameName.trim()}
            >
              确认重命名
            </AppButton>
          </div>
        }
      >
        <div className="space-y-4">
          <p className="text-sm opacity-70">
            为数据集 <strong>"原始名称"</strong> 输入新的名称：
          </p>
          <HeroInput
            label="数据集名称"
            value={renameName}
            onChange={setRenameName}
            placeholder="请输入新的数据集名称"
            labelPlacement="outside-top"
          />
        </div>
      </AppModal>
    </div>
  );
}

