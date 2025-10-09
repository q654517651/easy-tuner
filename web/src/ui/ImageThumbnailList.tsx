import { useState, useEffect } from "react";
import { Input, Card, CardFooter, Image } from "@heroui/react";
import ScrollArea from "./ScrollArea";

// 判断文件类型的工具函数
const isVideoFile = (filename: string): boolean => {
  const videoExts = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.webm', '.m4v'];
  const ext = filename.toLowerCase().slice(filename.lastIndexOf('.'));
  return videoExts.includes(ext);
};

interface MediaItem {
  id: string;
  filename: string;
  url: string;
  caption: string;
}

interface ImageThumbnailListProps {
  images: MediaItem[];
  selectedImageId?: string;
  onImageSelect: (imageId: string) => void;
}

interface ThumbnailItemProps {
  image: MediaItem;
  isSelected: boolean;
  onClick: () => void;
}

function ThumbnailItem({ image, isSelected, onClick }: ThumbnailItemProps) {
  const isVideo = isVideoFile(image.filename);

  return (
    <Card
      isPressable
      onPress={onClick}
      isFooterBlurred
      radius="lg"
      className={`
        border-none transition-all duration-200 cursor-pointer
        ${isSelected
          ? 'thumbnail-card-selected'
          : 'thumbnail-card-hover'
        }
      `}
    >
      {isVideo ? (
        <video
          src={image.url}
          className="object-cover aspect-square w-full"
          muted
          playsInline
          preload="metadata"
        />
      ) : (
        <Image
          alt={image.filename || "image"}
          src={image.url}
          radius="lg"
          classNames={{
            wrapper: "relative rounded-large aspect-square w-full shadow-none",
            img: "object-cover w-full h-full opacity-0 data-[loaded=true]:opacity-100 transition-opacity duration-300",
          }}
          loading="eager"
          fallbackSrc="data:image/gif;base64,R0lGODlhAQABAAAAACwAAAAAAQABAAA="
          onLoad={() => {/* 可选：埋点/日志 */}}
          onError={() => {/* 可选：上报 */}}
          removeWrapper
        />
      )}

      <CardFooter className="justify-center before:bg-white/10 border-white/20 border-1 overflow-hidden py-1 absolute before:rounded-xl rounded-large bottom-1 w-[calc(100%_-_8px)] shadow-small ml-1 z-10">
        <p className="text-tiny text-white/80 truncate" title={image.filename}>
          {image.filename}
        </p>
      </CardFooter>
    </Card>
  );
}

export default function ImageThumbnailList({ images, selectedImageId, onImageSelect }: ImageThumbnailListProps) {
  const [searchTerm, setSearchTerm] = useState("");

  // 过滤图片
  const filteredImages = images.filter(image =>
    image.filename.toLowerCase().includes(searchTerm.toLowerCase()) ||
    image.caption.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // 自动选择第一张图片
  useEffect(() => {
    if (!selectedImageId && filteredImages.length > 0) {
      onImageSelect(filteredImages[0].id);
    }
  }, [filteredImages, selectedImageId, onImageSelect]);

  return (
    <div className="flex flex-col h-full bg-transparent">
      {/* 图片网格 */}
      <div className="flex-1 min-h-0">
        <ScrollArea className="h-full">
          <div className="p-4" style={{ containerType: 'inline-size' }}>
        {filteredImages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-foreground-400">
            <svg className="w-12 h-12 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <p className="text-sm">
              {searchTerm ? "没有找到匹配的图片" : "暂无图片"}
            </p>
          </div>
        ) : (
          <div className="responsive-thumbnail-grid">
            {filteredImages.map((image) => (
              <ThumbnailItem
                key={image.id}
                image={image}
                isSelected={selectedImageId === image.id}
                onClick={() => onImageSelect(image.id)}
              />
            ))}
          </div>
        )}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}