import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";

export function useWebUiPrompts(filters: Record<string, unknown>) {
  return useQuery({ queryKey: ["web-ui-prompts", filters], queryFn: () => api.webUiPrompts(filters) });
}
