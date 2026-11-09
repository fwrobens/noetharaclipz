import { useEffect, useId, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { cn } from "@/lib/utils";

/**
 * A traveling, softly glowing highlight around a rounded container.
 * Inspired by Magic UI's BorderBeam, using an animated SVG dash rather
 * than spinning a full conic gradient. Container must be position: relative.
 */
export interface BorderBeamProps {
  size?: number;
  duration?: number;
  delay?: number;
  borderWidth?: number;
  radius?: number;
  colorFrom?: string;
  colorTo?: string;
  reverse?: boolean;
  className?: string;
  style?: CSSProperties;
}

export function BorderBeam({
  size = 80,
  duration = 8,
  delay = 0,
  borderWidth = 1.5,
  radius = 24,
  colorFrom = "#62b8ff",
  colorTo = "#b9efff",
  reverse = false,
  className,
  style,
}: BorderBeamProps) {
  const id = useId().replace(/:/g, "");
  const pathRef = useRef<SVGRectElement>(null);
  const [perimeter, setPerimeter] = useState(900);
  useEffect(() => {
    const path = pathRef.current;
    const parent = path?.ownerSVGElement?.parentElement;
    if (!path || !parent) return;
    const update = () => {
      if (typeof path.getTotalLength !== "function") return;
      const length = path.getTotalLength();
      if (Number.isFinite(length) && length > 0) setPerimeter(length);
    };
    update();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(update);
    observer.observe(parent);
    return () => observer.disconnect();
  }, [radius]);
  const dash = Math.max(2, Math.min(40, (Math.max(1, size) / perimeter) * 100));
  const common = {
    x: 1,
    y: 1,
    width: "calc(100% - 2px)",
    height: "calc(100% - 2px)",
    rx: radius,
    fill: "none" as const,
    pathLength: 100,
    vectorEffect: "non-scaling-stroke" as const,
  };
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      className={cn("noethara-border-beam pointer-events-none absolute inset-0 z-10 h-full w-full", className)}
      style={style}
    >
      <defs>
        <linearGradient id={id} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor={colorFrom} />
          <stop offset="45%" stopColor="#e9faff" />
          <stop offset="100%" stopColor={colorTo} />
        </linearGradient>
      </defs>
      <rect {...common} stroke="#8eb3cc" strokeOpacity="0.09" strokeWidth={borderWidth} />
      <rect
        {...common}
        ref={pathRef}
        className="noethara-border-beam__light"
        stroke={`url(#${id})`}
        strokeWidth={borderWidth}
        strokeLinecap="round"
        strokeDasharray={`${dash} ${100 - dash}`}
        style={{
          animationDuration: `${Math.max(1, duration)}s`,
          animationDelay: `-${Math.max(0, delay)}s`,
          animationDirection: reverse ? "reverse" : "normal",
        }}
      />
    </svg>
  );
}
