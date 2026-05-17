import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { ScheduledTaskPayload } from "../lib/types";

export function useScheduledTasks(filters: Record<string, unknown> = {}) {
  return useQuery({ queryKey: ["scheduled-tasks", filters], queryFn: () => api.scheduledTasks(filters), refetchInterval: 30000 });
}

export function useScheduledTaskRuns(taskId?: number, filters: Record<string, unknown> = {}) {
  return useQuery({
    queryKey: ["scheduled-task-runs", taskId, filters],
    queryFn: () => api.scheduledTaskRuns(taskId as number, filters),
    enabled: Boolean(taskId),
    refetchInterval: taskId ? 30000 : false
  });
}

export function useCreateScheduledTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ScheduledTaskPayload) => api.createScheduledTask(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scheduled-tasks"] })
  });
}

export function useUpdateScheduledTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: ScheduledTaskPayload }) => api.updateScheduledTask(id, payload),
    onSuccess: (_task, variables) => {
      queryClient.invalidateQueries({ queryKey: ["scheduled-tasks"] });
      queryClient.invalidateQueries({ queryKey: ["scheduled-task-runs", variables.id] });
    }
  });
}

export function useDeleteScheduledTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteScheduledTask(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scheduled-tasks"] })
  });
}

export function useRunScheduledTaskNow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.runScheduledTaskNow(id),
    onSuccess: (_run, id) => {
      queryClient.invalidateQueries({ queryKey: ["scheduled-tasks"] });
      queryClient.invalidateQueries({ queryKey: ["scheduled-task-runs", id] });
    }
  });
}
