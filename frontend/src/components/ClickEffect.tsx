import React, { useEffect } from 'react';

export const ClickEffect: React.FC = () => {
  useEffect(() => {
    const handlePointerDown = (e: PointerEvent) => {
      // Only trigger on primary mouse button (left click) or tap
      if (e.button !== 0) return;

      const ripple = document.createElement('div');
      ripple.className = 'click-ripple';
      ripple.style.left = `${e.clientX}px`;
      ripple.style.top = `${e.clientY}px`;

      document.body.appendChild(ripple);

      const cleanup = () => {
        if (ripple.parentNode) {
          ripple.remove();
        }
      };

      ripple.addEventListener('animationend', cleanup, { once: true });

      // Fallback cleanup in case animationend does not fire
      setTimeout(cleanup, 500);
    };

    window.addEventListener('pointerdown', handlePointerDown, { passive: true });

    return () => {
      window.removeEventListener('pointerdown', handlePointerDown);
    };
  }, []);

  return null;
};
