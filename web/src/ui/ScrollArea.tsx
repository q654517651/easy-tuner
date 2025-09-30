import React, {useEffect, useRef, useState} from "react";

type ScrollAreaProps = {
  className?: string;
  style?: React.CSSProperties;
  children: React.ReactNode;
  scrollerRef?: React.Ref<HTMLDivElement>;
  onScroll?: (e: React.UIEvent<HTMLDivElement>) => void;
  minThumbSize?: number;
};

// 自定义滚动区域：隐藏原生滚动条，右侧覆盖一条淡入拇指，滚动/悬浮时显示
export default function ScrollArea({
  className,
  style,
  children,
  scrollerRef,
  onScroll,
  minThumbSize = 20,
}: ScrollAreaProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [thumbH, setThumbH] = useState(0);
  const [thumbTop, setThumbTop] = useState(0);
  const [scrolling, setScrolling] = useState(false);
  const hideTimer = useRef<number | null>(null);

  // 合并外部 ref
  useEffect(() => {
    if (!scrollerRef) return;
    if (typeof scrollerRef === 'function') scrollerRef(scrollRef.current as HTMLDivElement);
    else if (typeof scrollerRef === 'object' && scrollerRef) (scrollerRef as any).current = scrollRef.current;
  }, [scrollerRef]);

  const recalc = () => {
    const el = scrollRef.current;
    const root = containerRef.current;
    if (!el || !root) return;
    const {scrollHeight, clientHeight, scrollTop} = el;
    const ratio = clientHeight / Math.max(scrollHeight, 1);
    const h = Math.max(Math.floor(clientHeight * ratio), minThumbSize);
    const maxTop = Math.max(clientHeight - h, 0);
    const top = (scrollTop / Math.max(scrollHeight - clientHeight, 1)) * maxTop;
    setThumbH(h);
    setThumbTop(top);
  };

  useEffect(() => {
    recalc();
    const el = scrollRef.current;
    if (!el) return;
    const onScrollInner = (e: Event) => {
      recalc();
      setScrolling(true);
      if (hideTimer.current) window.clearTimeout(hideTimer.current);
      hideTimer.current = window.setTimeout(() => setScrolling(false), 800);
      if (onScroll) (onScroll as any)(e);
    };
    el.addEventListener('scroll', onScrollInner, {passive: true});
    const RO = (window as any).ResizeObserver;
    const ro = RO ? new RO(() => recalc()) : null;
    if (ro) ro.observe(el);
    return () => {
      el.removeEventListener('scroll', onScrollInner as any);
      if (ro && typeof ro.disconnect === 'function') ro.disconnect();
    };
  }, [onScroll]);

  useEffect(() => {
    const r = () => recalc();
    window.addEventListener('resize', r);
    return () => window.removeEventListener('resize', r);
  }, []);

  return (
    <div ref={containerRef} className={["relative scrollarea", className || ""].join(" ")} style={style} data-scrolling={scrolling ? 'true' : undefined}>
      <div ref={scrollRef} className="no-native-scrollbar overflow-auto h-full">
        {children}
      </div>
      {/* 自定义拇指 */}
      <div className="sa-thumb" style={{height: thumbH, transform: `translateY(${thumbTop}px)`}} />
    </div>
  );
}
