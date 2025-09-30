import { useRef, useState, useCallback } from 'react';

export function useHoverVideo() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isHovering, setIsHovering] = useState(false);

  const handleMouseEnter = useCallback(() => {
    setIsHovering(true);
    if (videoRef.current) {
      videoRef.current.play().catch(() => {
        // 忽略播放失败（可能是用户交互策略限制）
      });
    }
  }, []);

  const handleMouseLeave = useCallback(() => {
    setIsHovering(false);
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.currentTime = 0;
    }
  }, []);

  return {
    videoRef,
    isHovering,
    hoverBind: {
      onMouseEnter: handleMouseEnter,
      onMouseLeave: handleMouseLeave
    }
  };
}