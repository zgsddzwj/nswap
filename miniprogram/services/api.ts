/**
 * 请求层（三模式，docs/13 路线 C）。
 * - 本地开发：wx.request 直连本地后端，请求头 X-DEV-OPENID 模拟身份
 * - 云托管生产：wx.cloud.callContainer，微信自动注入 X-WX-OPENID
 * - 自建服务器：wx.request 直连 HTTPS 域名，wx.login 换 token + Authorization 头；
 *   401（token 过期）自动静默重登并重放一次，用户无感
 *
 * 统一处理后端响应信封 {code, message, data} 与 422 校验错误的兜底。
 */
import { CONFIG, DEPLOY_MODE } from "../config/index";

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

// ---------- 登录 token（自建服务器模式） ----------

const TOKEN_KEY = "auth_token";

export function getAuthToken(): string {
  const v = wx.getStorageSync(TOKEN_KEY);
  return typeof v === "string" ? v : "";
}

export function setAuthToken(token: string) {
  wx.setStorageSync(TOKEN_KEY, token);
}

export function clearAuthToken() {
  wx.removeStorageSync(TOKEN_KEY);
}

let loginInFlight: Promise<any> | null = null;

/**
 * 自建模式静默登录：wx.login → code → /api/auth/login 换 token（并发去重）。
 * code 一次性且 5 分钟有效，失败后需重新 wx.login（本函数每次调用都会重新取 code）。
 */
export function silentLogin(): Promise<any> {
  if (loginInFlight) return loginInFlight;
  const p = new Promise<any>((resolve, reject) => {
    wx.login({
      success: (res) => {
        if (!res.code) {
          reject(new ApiError("微信登录失败，请重试", 0, 0));
          return;
        }
        // allowRelogin=false：登录请求本身失败不得再触发重登（防循环）
        requestOnce<any>("POST", "/api/auth/login", { code: res.code }, false)
          .then((data) => {
            if (data && data.token) setAuthToken(data.token);
            resolve(data);
          })
          .catch((e) => {
            clearAuthToken();
            reject(e);
          });
      },
      fail: () => reject(new ApiError("微信登录失败，请重试", 0, 0)),
    });
  });
  loginInFlight = p.then(
    (v) => {
      loginInFlight = null;
      return v;
    },
    (e) => {
      loginInFlight = null;
      throw e;
    }
  );
  return loginInFlight;
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
  return requestOnce<T>(method, path, data, true);
}

function requestOnce<T>(
  method: Method,
  path: string,
  data: Record<string, any> | undefined,
  allowRelogin: boolean
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const onBody = (status: number, body: any) => {
      if (DEPLOY_MODE === "self" && status === 401 && allowRelogin) {
        // token 过期：静默重登（wx.login 无感）后重放原请求一次
        silentLogin()
          .then(() => requestOnce<T>(method, path, data, false))
          .then(resolve)
          .catch(reject);
        return;
      }
      handleBody(status, body, resolve, reject);
    };

    if (DEPLOY_MODE === "local") {
      wx.request({
        url: CONFIG.DEV_BASE_URL + withQuery(path, method === "GET" ? data : undefined),
        method,
        data: method === "GET" ? undefined : data,
        header: { "content-type": "application/json", "X-DEV-OPENID": devOpenid() },
        success: (res) => onBody(res.statusCode, res.data),
        fail: () =>
          reject(
            new ApiError(
              "连不上后端服务：模拟器请确认后端已启动；真机请确认与电脑同一 Wi-Fi、地址为局域网 IP 且已打开调试",
              0,
              0
            )
          ),
      });
    } else if (DEPLOY_MODE === "self") {
      const token = getAuthToken();
      const header: Record<string, string> = { "content-type": "application/json" };
      if (token) header.Authorization = `Bearer ${token}`;
      wx.request({
        url:
          CONFIG.SELF_HOSTED_BASE_URL.replace(/\/$/, "") +
          withQuery(path, method === "GET" ? data : undefined),
        method,
        data: method === "GET" ? undefined : data,
        header,
        success: (res) => onBody(res.statusCode, res.data),
        fail: () => reject(new ApiError("网络请求失败，请检查网络后重试", 0, 0)),
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
        success: (res: any) => onBody(res.statusCode, res.data),
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
