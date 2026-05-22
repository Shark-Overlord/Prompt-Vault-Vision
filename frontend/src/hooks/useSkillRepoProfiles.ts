import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { SkillRepoProfile } from "../lib/types";

export function useSkillRepoProfiles(filters: Record<string, unknown>) {
  return useQuery({ queryKey: ["skill-repo-profiles", filters], queryFn: () => api.skillRepoProfiles(filters) });
}

export function useUpdateSkillRepoProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<SkillRepoProfile> }) => api.updateSkillRepoProfile(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["skill-repo-profiles"] });
    }
  });
}
