/**
 * 双模式请求层。
 * - 本地开发：wx.request 直连本地后端，请求头 X-DEV-OPENID 模拟身份
 * - 云托管生产：wx.cloud.callContainer，微信自动注入 X-WX-OPENID
 *
 * 统一处理后端响应信封 {code, message, data} 与 422 校验错误的兜底。
 */
import { CONFIG, LOCAL_DEV } from "../config/index";

export type Method = "GET" | "POST" | "PUT" | "DELETE";
// 注意：wx.request 不支持 PATCH（微信平台限制），后端为 arrange 提供了 PUT 别名

export class ApiError extends Error {
  /** HTTP 状态码（网络失败为 0） */
  status: number;
  /** 后端业务码（无信封时同 status） */
  code: number;
  constructor(message: string, status: number, code: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

/** 本地开发身份（「我的」页可切换，与 seed.py 演示用户一致） */
export function devOpenid(): string {
  const v = wx.getStorageSync("dev_openid");
  return typeof v === "string" && v ? v : "dev_alice";
}

export function setDevOpenid(openid: string) {
  wx.setStorageSync("dev_openid", openid);
}

function withQuery(path: string, params?: Record<string, any>): string {
  if (!params) return path;
  const qs = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join("&");
  if (!qs) return path;
  return path + (path.includes("?") ? "&" : "?") + qs;
}

function handleBody(status: number, body: any, resolve: Function, reject: Function) {
  if (status >= 200 && status < 300 && body && body.code === 0) {
    resolve(body.data);
    return;
  }
  if (body && typeof body.message === "string" && body.message) {
    reject(new ApiError(body.message, status, body.code ?? status));
    return;
  }
  if (body && Array.isArray(body.detail)) {
    // FastAPI 422 参数校验
    reject(new ApiError("填写内容有误，请检查后重试", status, 422));
    return;
  }
  reject(new ApiError(status === 404 ? "内容不存在或已删除" : "请求失败，请稍后重试", status, status));
}

export function request<T = any>(
  method: Method,
  path: string,
  data?: Record<string, any>
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    if (LOCAL_DEV) {
      wx.request({
        url: CONFIG.DEV_BASE_URL + withQuery(path, method === "GET" ? data : undefined),
        method,
        data: method === "GET" ? undefined : data,
        header: { "content-type": "application/json", "X-DEV-OPENID": devOpenid() },
        success: (res) => handleBody(res.statusCode, res.data, resolve, reject),
        fail: () =>
          reject(
            new ApiError(
              "无法连接本地服务，请确认后端已启动（docker-compose up）",
              0,
              0
            )
          ),
      });
    } else {
      wx.cloud.callContainer({
        config: { env: CONFIG.CLOUD_ENV },
        path: withQuery(path, method === "GET" ? data : undefined),
        method,
        header: {
          "X-WX-SERVICE": CONFIG.CLOUD_SERVICE,
          "content-type": "application/json",
        },
        data: method === "GET" ? undefined : data,
        success: (res: any) => handleBody(res.statusCode, res.data, resolve, reject),
        fail: () => reject(new ApiError("网络请求失败，请稍后重试", 0, 0)),
      });
    }
  });
}

export const get = <T = any>(path: string, params?: Record<string, any>) =>
  request<T>("GET", path, params);
export const post = <T = any>(path: string, data?: Record<string, any>) =>
  request<T>("POST", path, data);
export const put = <T = any>(path: string, data?: Record<string, any>) =>
  request<T>("PUT", path, data);
export const del = <T = any>(path: string, data?: Record<string, any>) =>
  request<T>("DELETE", path, data);

/** 统一错误提示（页面 catch 后调用） */
export function toastError(e: any) {
  const msg =
    e instanceof ApiError
      ? e.message
      : e && e.message
        ? String(e.message)
        : "操作失败，请稍后重试";
  wx.showToast({ title: msg, icon: "none", duration: 2200 });
}

/**
 * 订阅消息授权：用户 accept 后向后端登记配额。
 * 模板 ID 未配置时静默跳过（仅用站内通知）。
 */
export async function requestSubscribe(keys: Array<"want" | "accepted" | "confirm" | "review">) {
  const entries = keys
    .map((k) => ({ key: k, id: CONFIG.SUBSCRIBE_TEMPLATES[k] }))
    .filter((x) => !!x.id);
  if (!entries.length) return;
  try {
    const res = await wx.requestSubscribeMessage({ tmplIds: entries.map((x) => x.id) });
    for (const x of entries) {
      if (res[x.id] === "accept") {
        post("/api/notifications/subscribe", { template_key: x.key }).catch(() => {
          /* 登记失败不影响主流程 */
        });
      }
    }
  } catch {
    /* 用户拒绝或环境不支持时静默 */
  }
}
