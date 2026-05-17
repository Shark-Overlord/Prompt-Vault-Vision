import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { AgentMemoryPayload } from "../lib/types";

export function useAgentThreads() {
  return useQuery({ queryKey: ["agent-threads"], queryFn: api.agentThreads });
}

export function useAgentMessages(threadId?: string | null) {
  return useQuery({
    queryKey: ["agent-messages", threadId],
    queryFn: () => api.agentMessages(threadId as string),
    enabled: Boolean(threadId)
  });
}

export function useAgentChat() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.agentChat,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["agent-threads"] });
      queryClient.invalidateQueries({ queryKey: ["agent-messages", result.thread_id] });
      queryClient.invalidateQueries({ queryKey: ["agent-memories"] });
    }
  });
}

export function useAgentMemories(filters: Record<string, unknown> = {}) {
  return useQuery({ queryKey: ["agent-memories", filters], queryFn: () => api.agentMemories(filters) });
}

export function useCreateAgentMemory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AgentMemoryPayload) => api.createAgentMemory(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["agent-memories"] })
  });
}

export function useApproveAgentMemory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.approveAgentMemory(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["agent-memories"] })
  });
}

export function useRejectAgentMemory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.rejectAgentMemory(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["agent-memories"] })
  });
}

export function useDeleteAgentMemory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteAgentMemory(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["agent-memories"] })
  });
}
