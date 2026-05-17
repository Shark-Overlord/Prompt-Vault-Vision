import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { AnnotationRunCreate, AnnotationRunUpdate, AnnotationSuggestionPatch } from "../lib/types";

export function useAnnotationQueue(filters: Record<string, unknown>) {
  return useQuery({ queryKey: ["annotation-queue", filters], queryFn: () => api.annotationQueue(filters) });
}

export function useAnnotationRuns(filters: Record<string, unknown>) {
  return useQuery({ queryKey: ["annotation-runs", filters], queryFn: () => api.annotationRuns(filters), refetchInterval: 2000 });
}

export function useAnnotationSuggestions(filters: Record<string, unknown>) {
  return useQuery({ queryKey: ["annotation-suggestions", filters], queryFn: () => api.annotationSuggestions(filters) });
}

export function useCreateAnnotationRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AnnotationRunCreate) => api.createAnnotationRun(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["annotation-runs"] });
      queryClient.invalidateQueries({ queryKey: ["annotation-suggestions"] });
    }
  });
}

export function useCancelAnnotationRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.cancelAnnotationRun(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["annotation-runs"] });
      queryClient.invalidateQueries({ queryKey: ["annotation-queue"] });
      queryClient.invalidateQueries({ queryKey: ["annotation-suggestions"] });
    }
  });
}

export function useAnnotationRunActions() {
  const queryClient = useQueryClient();
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["annotation-runs"] });
    queryClient.invalidateQueries({ queryKey: ["annotation-queue"] });
    queryClient.invalidateQueries({ queryKey: ["annotation-suggestions"] });
  };
  const update = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: AnnotationRunUpdate }) => api.updateAnnotationRun(id, payload),
    onSuccess: invalidate
  });
  const pause = useMutation({
    mutationFn: (id: number) => api.pauseAnnotationRun(id),
    onSuccess: invalidate
  });
  const rerun = useMutation({
    mutationFn: (id: number) => api.rerunAnnotationRun(id),
    onSuccess: invalidate
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.deleteAnnotationRun(id),
    onSuccess: invalidate
  });
  return { update, pause, rerun, remove };
}

export function useAnnotationSuggestionActions() {
  const queryClient = useQueryClient();
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["annotation-suggestions"] });
    queryClient.invalidateQueries({ queryKey: ["annotation-queue"] });
    queryClient.invalidateQueries({ queryKey: ["prompt-pairs"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };
  const update = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: AnnotationSuggestionPatch }) => api.updateAnnotationSuggestion(id, payload),
    onSuccess: invalidate
  });
  const accept = useMutation({
    mutationFn: (id: number) => api.acceptAnnotationSuggestion(id),
    onSuccess: invalidate
  });
  const reject = useMutation({
    mutationFn: (id: number) => api.rejectAnnotationSuggestion(id),
    onSuccess: invalidate
  });
  return { update, accept, reject };
}
