import { useRef } from 'react';

// react-bits SpotlightCard 暖纸适配（零依赖，CSS 移入 styles.css）。
// 悬停时径向聚光随鼠标移动；focus-within 同样触发（键盘可达）。
export default function SpotlightCard({ children, className = '', spotlightColor = 'rgba(253, 180, 140, 0.14)' }) {
  const ref = useRef(null);

  const move = (e) => {
    const rect = ref.current.getBoundingClientRect();
    ref.current.style.setProperty('--mouse-x', `${e.clientX - rect.left}px`);
    ref.current.style.setProperty('--mouse-y', `${e.clientY - rect.top}px`);
    ref.current.style.setProperty('--spotlight-color', spotlightColor);
  };

  return (
    <div ref={ref} onMouseMove={move} className={`card-spotlight ${className}`}>
      {children}
    </div>
  );
}
