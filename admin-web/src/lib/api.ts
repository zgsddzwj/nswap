/** 管理后台 API 封装：信封拆解、401 跳登录、错误 toast */
import { toast } from "sonner";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export interface Envelope<T> {
  code: number;
  message: string;
  data: T;
}

export async function api<T = unknown>(
  method: "GET" | "POST" | "PUT" | "DELETE" | "PATCH",
  path: string,
  body?: unknown
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      method,
      credentials: "include",
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("网络请求失败，请检查后端服务", 0);
  }
  let payload: Envelope<T> | null = null;
  try {
    payload = (await res.json()) as Envelope<T>;
  } catch {
    /* 非 JSON 响应 */
  }
  if (res.status === 401) {
    // 会话失效：跳登录页（登录页自身除外）
    if (!location.pathname.endsWith("/login")) {
      location.href = "/admin/login";
    }
    throw new ApiError(payload?.message || "请先登录", 401);
  }
  if (!res.ok || !payload || payload.code !== 0) {
    throw new ApiError(payload?.message || `请求失败（${res.status}）`, res.status);
  }
  return payload.data;
}

export function toastError(e: unknown) {
  toast.error(e instanceof Error ? e.message : "操作失败，请稍后重试");
}

export interface Page<T> {
  list: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminInfo {
  id: number;
  username: string;
  name: string;
  role: "super" | "community";
  community: { id: number; name: string; city: string } | null;
}
