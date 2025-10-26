# 控制图智能拖拽上传功能

## 📋 功能说明

前端现在支持智能识别控制图文件名，自动分类上传到对应的目录。

## ✨ 功能特性

### 1. 智能识别控制图命名

当拖拽文件到**控制图数据集**（`single_control_image` 或 `multi_control_image`）时，前端会自动识别以下命名格式：

#### 支持的控制图命名格式

```
✅ image1_0.png      - 单位数索引
✅ image1_1.jpg      - 单位数索引
✅ image1_0000.png   - 四位数索引
✅ image1_0001.webp  - 四位数索引
✅ photo_00.jpg      - 两位数索引
✅ test_999.bmp      - 任意位数索引
```

**命名规则**：`basename_数字.扩展名`
- `basename`：原图的文件名（不含扩展名）
- `数字`：控制图索引（支持任意位数）
- `扩展名`：支持 jpg、jpeg、png、webp、bmp

### 2. 自动分类上传

#### 控制图数据集

拖拽文件时自动分类：

```
拖入文件：
  - image1.jpg       → 普通图片，上传到 images/ 目录
  - image1_0.png     → 控制图，上传到 controls/ 目录
  - image1_1.png     → 控制图，上传到 controls/ 目录
  - photo2.jpg       → 普通图片，上传到 images/ 目录
  - photo2_0000.jpg  → 控制图，上传到 controls/ 目录
```

#### 普通图片数据集

所有文件都作为普通图片上传：

```
拖入文件：
  - image1.jpg       → 普通图片，上传到 images/ 目录
  - image1_0.png     → 普通图片，上传到 images/ 目录（不识别为控制图）
  - photo2.jpg       → 普通图片，上传到 images/ 目录
```

### 3. 自动匹配原图

控制图会自动匹配对应的原图：

```
现有图片：
  - image1.jpg
  - photo2.png

拖入控制图：
  - image1_0.png   ✅ 匹配 image1.jpg，上传成功
  - image1_1.jpg   ✅ 匹配 image1.jpg，上传成功
  - photo2_0.png   ✅ 匹配 photo2.png，上传成功
  - image3_0.png   ❌ 没有找到 image3.*，跳过并提示
```

**匹配规则**：
- 控制图的 basename 必须与数据集中已存在的某个图片的 basename 相同
- 支持不同扩展名匹配（如 image1.jpg 可以匹配 image1_0.png）

## 🎯 使用场景

### 场景 1：批量上传原图和控制图

```
1. 创建控制图数据集
2. 一次性拖入所有文件：
   - image1.jpg, image1_0.png, image1_1.png
   - image2.jpg, image2_0.png, image2_1.png
   - image3.jpg, image3_0.png
3. 前端自动分类：
   - 先上传原图 (image1.jpg, image2.jpg, image3.jpg)
   - 再上传控制图并自动关联
```

### 场景 2：后续添加控制图

```
1. 数据集已有原图
2. 直接拖入控制图：
   - image1_0.png
   - image1_1.png
3. 自动匹配并上传
```

### 场景 3：混合上传

```
拖入文件：
  - newimage.jpg      → 新原图
  - newimage_0.png    → 控制图（匹配刚上传的 newimage.jpg）
  - oldimage_2.png    → 控制图（匹配已存在的 oldimage.jpg）
```

## ⚠️ 注意事项

### 1. 原图必须先存在

控制图上传时，必须在数据集中能找到对应的原图：

```
❌ 错误顺序：先拖入 image1_0.png，但 image1.jpg 不存在
✅ 正确顺序：确保 image1.jpg 已存在，再拖入 image1_0.png

或者：
✅ 一次性拖入：image1.jpg 和 image1_0.png 一起拖入
   （前端会先上传原图，再上传控制图）
```

### 2. 命名必须规范

```
✅ 正确命名：
  - image1_0.png
  - image1_1.png
  - photo_0000.jpg

❌ 错误命名（不会被识别为控制图）：
  - image1-0.png    （使用了连字符 - 而不是下划线 _）
  - image1_a.png    （索引不是数字）
  - image1_.png     （缺少索引数字）
```

### 3. 数据集类型限制

只有以下数据集类型支持智能识别：
- ✅ `single_control_image` - 单图控制数据集
- ✅ `multi_control_image` - 多图控制数据集
- ❌ `image` - 普通图片数据集（所有文件都作为普通图片）
- ❌ `video` - 视频数据集

## 🔧 技术实现

### 识别逻辑

```typescript
// 正则表达式匹配控制图命名
const match = file.name.match(/^(.+?)_(\d+)\.(jpg|jpeg|png|webp|bmp)$/i);

if (match) {
  const basename = match[1];   // 提取 basename
  const index = parseInt(match[2]);  // 提取索引
  // 识别为控制图
}
```

### 上传流程

```
1. 检查数据集类型
   ↓
2. 如果是控制图数据集：
   ├─ 分类文件（控制图 vs 普通图片）
   ├─ 先上传普通图片
   ├─ 刷新数据集获取最新图片列表
   ├─ 逐个上传控制图并匹配原图
   └─ 刷新界面显示结果
   
3. 如果不是控制图数据集：
   └─ 所有文件作为普通图片上传
```

## 📊 上传结果提示

### 成功提示

```
✅ 上传成功
成功上传 5 个文件（含控制图）
```

### 部分失败提示

```
⚠️ 部分上传失败
3 个文件上传失败

错误详情（控制台）：
- 控制图 image3_0.png 没有找到对应的原图 image3.*
- 控制图 photo_0.jpg 上传失败: HTTP 400
```

## 🚀 未来增强

可能的功能增强：
1. 支持拖入文件夹，自动递归扫描
2. 支持更多命名格式（如 image1.control0.png）
3. 原图不存在时自动创建占位图
4. 批量重命名工具

## 📝 更新日志

**v0.0.2** (2025-01-26)
- ✨ 新增：控制图智能识别和自动分类上传
- ✨ 支持 `basename_数字` 命名格式（任意位数）
- ✨ 自动匹配原图并关联控制图
- ✨ 混合上传：原图和控制图可一次性拖入

---

**提示**：此功能仅在前端实现，后端 API 保持不变。

