/**
 * useScrollProgress.ts
 * Tracks page scroll as a 0..1 progress value in a ref (read every frame by the
 * 3D camera rig, so it must NOT trigger React re-renders) plus a throttled
 * `section` index in state that only updates when the active story section
 * changes — this drives the HTML overlay copy without re-rendering per pixel.
 */
import { useEffect, useRef, useState } from 'react';

export interface ScrollProgress {
  /** Live 0..1 scroll progress, updated on scroll — read via .current. */
  progress: React.MutableRefObject<number>;
  /** Index of the currently active full-height section (0..sectionCount-1). */
  section: number;
}

export function useScrollProgress(sectionCount: number): ScrollProgress {
  const progress = useRef(0);
  const [section, setSection] = useState(0);

  useEffect(() => {
    let raf = 0;
    const update = () => {
      raf = 0;
      const doc = document.documentElement;
      const max = doc.scrollHeight - doc.clientHeight;
      const p = max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0;
      progress.current = p;
      const next = Math.min(sectionCount - 1, Math.floor(p * sectionCount + 0.001));
      setSection((prev) => (prev !== next ? next : prev));
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };
    update();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    return () => {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [sectionCount]);

  return { progress, section };
}
