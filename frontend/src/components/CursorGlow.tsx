import { useEffect, useRef } from "react";

/**
 * Soft multi-stop radial glow that follows the cursor at ~60fps via rAF.
 * Intentionally low opacity so it never competes with content.
 */
export function CursorGlow() {
  const glowRef = useRef<HTMLDivElement>(null);
  const pos = useRef({ x: -999, y: -999 });
  const target = useRef({ x: -999, y: -999 });
  const raf = useRef<number>(0);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      target.current.x = e.clientX;
      target.current.y = e.clientY;
    };

    const tick = () => {
      // Light lerp for butter-smooth motion without laggy feel
      pos.current.x += (target.current.x - pos.current.x) * 0.18;
      pos.current.y += (target.current.y - pos.current.y) * 0.18;
      const el = glowRef.current;
      if (el) {
        el.style.transform = `translate3d(${pos.current.x - 220}px, ${pos.current.y - 220}px, 0)`;
      }
      raf.current = requestAnimationFrame(tick);
    };

    window.addEventListener("mousemove", onMove, { passive: true });
    raf.current = requestAnimationFrame(tick);
    return () => {
      window.removeEventListener("mousemove", onMove);
      cancelAnimationFrame(raf.current);
    };
  }, []);

  return <div ref={glowRef} className="cursor-glow" aria-hidden="true" />;
}
