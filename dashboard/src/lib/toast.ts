/** Ergonomic API over the toast store. Callable from anywhere — React
 *  components, plain functions, the query cache, the api layer. */

import { useToastStore, type ToastInput } from "./toastStore";

type Opts = Omit<ToastInput, "kind" | "title" | "detail">;

function push(kind: ToastInput["kind"], title: string, detail?: string, opts?: Opts): number {
  return useToastStore.getState().push({ kind, title, detail, ...opts });
}

export const toast = {
  success: (title: string, detail?: string, opts?: Opts) => push("success", title, detail, opts),
  error: (title: string, detail?: string, opts?: Opts) => push("error", title, detail, opts),
  info: (title: string, detail?: string, opts?: Opts) => push("info", title, detail, opts),
  warning: (title: string, detail?: string, opts?: Opts) => push("warning", title, detail, opts),
  dismiss: (id: number) => useToastStore.getState().dismiss(id),
};

/** Normalize any thrown value to a display string. */
export function errMessage(e: unknown): string {
  if (e instanceof Error) return e.message;
  if (typeof e === "string") return e;
  try {
    return JSON.stringify(e);
  } catch {
    // Non-serializable throw value — fall back to coercion.
    return String(e);
  }
}
