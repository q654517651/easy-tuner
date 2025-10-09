import React from "react";

type EmptyStateProps = {
  image: string;
  message: string;
  className?: string;
  imageAlt?: string;
};

// 通用空状态：居中展示占位图 + 一句文案
const EmptyState: React.FC<EmptyStateProps> = ({ image, message, className, imageAlt }) => {
  return (
    <div className={["w-full min-h-[50vh] flex items-center justify-center", className || ""].join(" ")}> 
      <div className="flex flex-col items-center text-center">
        <img src={image} alt={imageAlt || "empty"} loading="lazy" decoding="async" className="w-40 h-40 object-contain opacity-90" draggable={false} />
        <div className="mt-4 text-gray-500 text-sm">{message}</div>
      </div>
    </div>
  );
};

export default EmptyState;
