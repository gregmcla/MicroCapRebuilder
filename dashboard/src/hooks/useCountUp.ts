import { useState, useEffect, useRef } from "react";

/**
 * Animates a number from 0 to `target` over `duration`ms with cubic ease-out.
 * Returns a formatted string (toFixed(decimals)).
 */
export function useCountUp(target: number, duration = 1200, decimals = 0): string {
  const [value, setValue] = useState(0);
  const startTimeRef = useRef<number | null>(null);
  const rafRef = useRef<number | null>(null);
  const prevTargetRef = useRef<number>(target);

  useEffect(() => {
    // Reset on target change
    const startFrom = value; // animate from current value
    const diff = target - startFrom;
    startTimeRef.current = null;
    prevTargetRef.current = target;

    function tick(ts: number) {
      if (startTimeRef.current === null) startTimeRef.current = ts;
      const elapsed = ts - startTimeRef.current;
      const progress = Math.min(elapsed / duration, 1);
      // Cubic ease-out: 1 - (1 - t)^3
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(startFrom + diff * eased);
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick);
      }
    }

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, [target, duration]);

  return value.toFixed(decimals);
}
