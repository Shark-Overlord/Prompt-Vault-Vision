import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { RepoScanPayload } from "../lib/types";

export function useRepos(filters: Record<string, unknown>) {
  return useQuery({ queryKey: ["repos", filters], queryFn: () => api.repos(filters) });
}

export function useScanRepo() {
  return useMutation({
    mutationFn: (input: number | { id: number; payload?: RepoScanPayload }) =>
      typeof input === "number" ? api.scanRepo(input) : api.scanRepo(input.id, input.payload)
  });
}

export function useCreateRepo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.createRepo,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repos"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  });
}

export function useUpdateRepo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Parameters<typeof api.updateRepo>[1] }) => api.updateRepo(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repos"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  });
}

export function useDeleteRepo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteRepo(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repos"] });
      queryClient.invalidateQueries({ queryKey: ["prompt-pairs"] });
      queryClient.invalidateQueries({ queryKey: ["pair-candidates"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  });
}

export function useBatchDeleteRepos() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ids: number[]) => api.batchDeleteRepos(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repos"] });
      queryClient.invalidateQueries({ queryKey: ["prompt-pairs"] });
      queryClient.invalidateQueries({ queryKey: ["pair-candidates"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  });
}

export function useBatchScanRepos() {
  return useMutation({
    mutationFn: (ids: number[]) => api.batchScanRepos(ids)
  });
}

export function useCancelRepoScanRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.cancelRepoScanRun(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repos"] });
      queryClient.invalidateQueries({ queryKey: ["prompt-pairs"] });
      queryClient.invalidateQueries({ queryKey: ["pair-candidates"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  });
}

export function useBatchDeleteRepoScanRuns() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ids: number[]) => api.batchDeleteRepoScanRuns(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repo-scan-runs"] });
    }
  });
}
