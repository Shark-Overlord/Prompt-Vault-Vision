import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";

export function useAssets(filters: Record<string, unknown>) {
  return useQuery({ queryKey: ["assets", filters], queryFn: () => api.assets(filters) });
}
