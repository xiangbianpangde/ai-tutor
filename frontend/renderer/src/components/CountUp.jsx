import { useState, useEffect } from 'react';

// react-bits Counter/CountUp 暖纸适配：零依赖（rAF 驱动，无 framer-motion）。
// 数字从 from 滚动到 to（约 800ms，easeOut），尊重 prefers-reduced-motion。
export default function CountUp({ to, from = 0, duration = 800, suffix = '', decimals = 0 }) {
  const [value, setValue] = useState(from);
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    setReduced(window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }, []);

  useEffect(() => {
    if (reduced) { setValue(to); return; }
    let raf = 0;
    const start = performance.now();
    const step = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3); // easeOutCubic
      setValue(from + (to - from) * eased);
      if (t < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [to, from, duration, reduced]);

  return <span className="count-up">{value.toFixed(decimals)}{suffix}</span>;
}
