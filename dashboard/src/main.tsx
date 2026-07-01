import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import {
  QueryClient,
  QueryCache,
  MutationCache,
  QueryClientProvider,
} from "@tanstack/react-query";
import "./index.css";
import App from "./App.tsx";
import { toast, errMessage } from "./lib/toast";

function hashKey(key: unknown): string {
  try {
    return JSON.stringify(key);
  } catch {
    // Non-serializable query key — coerce for a best-effort dedupe key.
    return String(key);
  }
}

const queryClient = new QueryClient({
  // Surface every read failure as a toast. Deduped by query key so a failing
  // poll (e.g. the 5s portfolio-state refetch) shows one toast, not a stream.
  // A query can opt out with `meta: { silentError: true }`.
  queryCache: new QueryCache({
    onError: (error, query) => {
      if (query.meta?.silentError) return;
      toast.error("Couldn’t load data", errMessage(error), {
        dedupeKey: `query:${hashKey(query.queryKey)}`,
      });
    },
  }),
  // Catch-all for mutation failures. Components may still show inline errors;
  // this guarantees no user action fails completely silently.
  mutationCache: new MutationCache({
    onError: (error) => {
      toast.error("Action failed", errMessage(error));
    },
  }),
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 10_000,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
