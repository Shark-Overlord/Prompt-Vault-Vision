import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { AiConfigPayload } from "../lib/types";

export function useAiConfigs() {
  return useQuery({ queryKey: ["ai-configs"], queryFn: api.aiConfigs });
}

export function useCreateAiConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AiConfigPayload) => api.createAiConfig(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ai-configs"] })
  });
}

export function useUpdateAiConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: AiConfigPayload }) => api.updateAiConfig(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ai-configs"] })
  });
}

export function useDeleteAiConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteAiConfig(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ai-configs"] })
  });
}

export function useTestAiConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.testAiConfig(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ai-configs"] })
  });
}

export function useAiConfigModels() {
  return useMutation({
    mutationFn: (id: number) => api.aiConfigModels(id)
  });
}
