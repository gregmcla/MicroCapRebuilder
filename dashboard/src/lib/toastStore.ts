/** Toast notification store — global, ephemeral user feedback.
 *  Rendered by <Toaster /> (mounted once in App) and driven via lib/toast.ts.
 *  Callable from non-React code (api layer, query cache) via getState().push. */

import { create } from "zustand";

export type ToastKind = "success" | "error" | "info" | "warning";

export interface ToastAction {
  label: string;
  onClick: () => void;
}

export interface Toast {
  id: number;
  kind: ToastKind;
  title: string;
  detail?: string;
  action?: ToastAction;
  /** ms before auto-dismiss; 0 = sticky (dismiss manually). */
  duration: number;
  /** Collapse repeat notifications (e.g. a failing 5s poll) into one toast. */
  dedupeKey?: string;
  createdAt: number;
}

export interface ToastInput {
  kind: ToastKind;
  title: string;
  detail?: string;
  action?: ToastAction;
  duration?: number;
  dedupeKey?: string;
}

interface ToastStore {
  toasts: Toast[];
  push: (t: ToastInput) => number;
  dismiss: (id: number) => void;
  clear: () => void;
}

const DEFAULT_DURATION: Record<ToastKind, number> = {
  success: 4000,
  info: 4000,
  warning: 6000,
  error: 8000,
};

let seq = 0;

export const useToastStore = create<ToastStore>((set, get) => ({
  toasts: [],
  push: (input) => {
    const now = Date.now();
    const duration = input.duration ?? DEFAULT_DURATION[input.kind];

    // Dedupe: if an un-dismissed toast shares this key, refresh it in place
    // instead of stacking a duplicate (prevents failing-poll toast spam).
    if (input.dedupeKey) {
      const existing = get().toasts.find((t) => t.dedupeKey === input.dedupeKey);
      if (existing) {
        set((s) => ({
          toasts: s.toasts.map((t) =>
            t.id === existing.id ? { ...t, ...input, duration, createdAt: now } : t,
          ),
        }));
        return existing.id;
      }
    }

    const id = ++seq;
    const toast: Toast = { ...input, id, duration, createdAt: now };
    set((s) => ({ toasts: [...s.toasts, toast] }));
    return id;
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
  clear: () => set({ toasts: [] }),
}));
