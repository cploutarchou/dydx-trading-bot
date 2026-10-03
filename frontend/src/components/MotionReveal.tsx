import React, { useEffect, useMemo, useRef, useState } from 'react';

interface MotionRevealProps {
  as?: React.ElementType;
  children: React.ReactNode;
  className?: string;
  delayMs?: number;
  distancePx?: number;
  once?: boolean;
}

export const MotionReveal: React.FC<MotionRevealProps> = ({
  as = 'div',
  children,
  className = '',
  delayMs = 0,
  distancePx = 24,
  once = true,
}) => {
  const ref = useRef<HTMLElement | null>(null);
  const [isVisible, setIsVisible] = useState(
    () =>
      typeof window === 'undefined' || window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );

  useEffect(() => {
    // Re-derived here (not read from state) so the observer setup is stable
    // across visibility flips.
    if (
      typeof window === 'undefined' ||
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
      return undefined;
    }

    const element = ref.current;
    if (!element) {
      return undefined;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setIsVisible(true);
            if (once) {
              observer.disconnect();
            }
          } else if (!once) {
            setIsVisible(false);
          }
        }
      },
      { threshold: 0.18, rootMargin: '0px 0px -8% 0px' }
    );

    observer.observe(element);

    return () => observer.disconnect();
  }, [once]);

  const style = useMemo(
    () =>
      ({
        '--reveal-delay': `${delayMs}ms`,
        '--reveal-distance': `${distancePx}px`,
      }) as React.CSSProperties,
    [delayMs, distancePx]
  );

  const classes = ['reveal-block', isVisible ? 'is-visible' : '', className]
    .filter(Boolean)
    .join(' ');
  const Component = as as React.ElementType;

  return (
    <Component ref={ref} className={classes} style={style}>
      {children}
    </Component>
  );
};
