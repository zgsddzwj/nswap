import { useQuery } from "@tanstack/react-query";
import { api, type AdminInfo } from "./api";

export function useAdmin() {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => api<AdminInfo>("GET", "/api/admin/auth/me"),
    retry: false,
    staleTime: 60_000,
  });
}
