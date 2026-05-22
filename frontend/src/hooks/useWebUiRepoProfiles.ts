import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { WebUiRepoProfile } from "../lib/types";

export function useWebUiRepoProfiles(filters: Record<string, unknown>) {
  return useQuery({ queryKey: ["web-ui-repo-profiles", filters], queryFn: () => api.webUiRepoProfiles(filters) });
}

export function useUpdateWebUiRepoProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<WebUiRepoProfile> }) => api.updateWebUiRepoProfile(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["web-ui-repo-profiles"] });
    }
  });
}
