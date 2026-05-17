import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";

export function useGithubAuth() {
  return useQuery({ queryKey: ["github-auth"], queryFn: api.githubAuthStatus });
}

export function useSaveGithubClientId() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.saveGithubClientId,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["github-auth"] })
  });
}

export function useStartGithubDevice() {
  return useMutation({ mutationFn: api.startGithubDevice });
}

export function usePollGithubDevice() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.pollGithubDevice,
    onSuccess: (data) => {
      if (data.status === "connected") queryClient.invalidateQueries({ queryKey: ["github-auth"] });
    }
  });
}

export function useLogoutGithub() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.logoutGithub,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["github-auth"] })
  });
}
