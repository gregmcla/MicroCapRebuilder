import { useState, useEffect, useRef } from "react";

export type FlashDir = "up" | "down" | null;

/**
 * Pulses when `value` changes — the classic "live ticker" cue.
 *
 * Returns { dir, nonce }: `dir` is the direction of the last change, `nonce`
 * increments on every change so a keyed element can replay its CSS animation
 * even when the direction repeats. Pass `value` at display precision
 * (e.g. Number(x.toFixed(2))) so it only fires when the *shown* number moves.
 * No flash on first mount; NaN transitions are ignored.
 */
export function useValueFlash(value: number): { dir: FlashDir; nonce: number } {
  const prevRef = useRef(value);
  const [state, setState] = useState<{ dir: FlashDir; nonce: number }>({ dir: null, nonce: 0 });

  useEffect(() => {
    const prev = prevRef.current;
    if (value === prev || Number.isNaN(value) || Number.isNaN(prev)) {
      prevRef.current = value;
      return;
    }
    prevRef.current = value;
    setState((s) => ({ dir: value > prev ? "up" : "down", nonce: s.nonce + 1 }));
  }, [value]);

  return state;
}
