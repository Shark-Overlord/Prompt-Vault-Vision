import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { RepoScanTemplate } from "../lib/types";

export function useRepoScanTemplates(repoId?: number | null) {
  return useQuery({
    queryKey: ["repo-scan-templates", repoId],
    queryFn: () => api.repoScanTemplates(repoId as number),
    enabled: Boolean(repoId)
  });
}

export function useGenerateRepoScanTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ repoId, aiConfigId }: { repoId: number; aiConfigId?: number | null }) => api.generateRepoScanTemplate(repoId, aiConfigId),
    onSuccess: (template) => {
      queryClient.invalidateQueries({ queryKey: ["repo-scan-templates", template.repo_id] });
      queryClient.invalidateQueries({ queryKey: ["repos"] });
    }
  });
}

export function useApproveRepoScanTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.approveRepoScanTemplate(id),
    onSuccess: (template) => {
      queryClient.invalidateQueries({ queryKey: ["repo-scan-templates", template.repo_id] });
    }
  });
}

export function useRejectRepoScanTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.rejectRepoScanTemplate(id),
    onSuccess: (template) => {
      queryClient.invalidateQueries({ queryKey: ["repo-scan-templates", template.repo_id] });
    }
  });
}

export function useUpdateRepoScanTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<RepoScanTemplate> }) => api.updateRepoScanTemplate(id, payload),
    onSuccess: (template) => {
      queryClient.invalidateQueries({ queryKey: ["repo-scan-templates", template.repo_id] });
    }
  });
}
