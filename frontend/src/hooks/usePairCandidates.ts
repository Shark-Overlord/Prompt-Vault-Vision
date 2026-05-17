import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";

export function usePairCandidates(filters: Record<string, unknown>) {
  return useQuery({ queryKey: ["pair-candidates", filters], queryFn: () => api.pairCandidates(filters) });
}

export function usePairCandidateActions() {
  const queryClient = useQueryClient();
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["pair-candidates"] });
    queryClient.invalidateQueries({ queryKey: ["prompt-pairs"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };

  const accept = useMutation({
    mutationFn: ({ id, selection_status = "pending_review" }: { id: number; selection_status?: string }) =>
      api.acceptPairCandidate(id, { selection_status }),
    onSuccess: invalidate
  });

  const reject = useMutation({
    mutationFn: (id: number) => api.rejectPairCandidate(id),
    onSuccess: invalidate
  });

  const update = useMutation({
    mutationFn: ({ id, review_status, review_reason }: { id: number; review_status: string; review_reason?: string }) =>
      api.updatePairCandidate(id, { review_status, review_reason }),
    onSuccess: invalidate
  });

  return { accept, reject, update };
}
