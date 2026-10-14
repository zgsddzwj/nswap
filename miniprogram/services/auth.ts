/** 身份与会话：启动静默登录、me 缓存与订阅、未读角标 */
import { get, post } from "./api";

export interface UserStats {
  sell_done: number;
  give_done: number;
  swap_done: number;
  review_good: number;
  review_mid: number;
  review_bad: number;
  thanks_count: number;
  violations: number;
}

export interface UserSummary {
  id: number;
  nickname: string;
  avatar_url: string;
  building: string;
  community_name?: string;
  verified: boolean;
  role: string;
  stats: UserStats;
  created_at: string;
}

export interface Me {
  user: UserSummary & {
    unit?: string;
    status: string;
    community_id?: number | null;
    agreed_terms_version?: string;
  };
  community: { id: number; name: string; verified_count: number; item_count: number } | null;
  unread_count: number;
  terms_version?: string;
}

let me: Me | null = null;
const listeners = new Set<(me: Me | null) => void>();

function emit() {
  listeners.forEach((fn) => fn(me));
}

export function getMe(): Me | null {
  return me;
}

export function onMeChange(fn: (me: Me | null) => void): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

/** 启动静默登录：后端按 openid 自动建档（首次生成「邻居xxxx」昵称） */
export async function ensureLogin(): Promise<Me | null> {
  try {
    me = await post<Me>("/api/auth/login");
    emit();
    return me;
  } catch (e) {
    console.error("[auth] login failed:", e);
    return null;
  }
}

export async function refreshMe(): Promise<Me | null> {
  try {
    me = await get<Me>("/api/me");
    emit();
    return me;
  } catch (e) {
    return null;
  }
}

export function setMe(next: Me) {
  me = next;
  emit();
}

/**
 * 准入制守卫（docs/10 修订）：未加入小区（未验证）的游客统一停在验证页，
 * 不进入任何内容页——避免各页 403 闪烁。已加入/请求失败（网络错误防死循环）返回 false。
 */
export function redirectIfNotVerified(me: Me | null): boolean {
  if (me && !me.user.verified) {
    wx.reLaunch({ url: "/pages/verify/verify" });
    return true;
  }
  return false;
}

/** 消息 tab 未读角标（home/mine/messages 的 onShow 调用） */
export async function refreshUnreadBadge() {
  try {
    const r = await get<{ unread_count: number }>("/api/me/unread");
    const n = r.unread_count || 0;
    if (n > 0) {
      wx.setTabBarBadge({ index: 2, text: String(Math.min(n, 99)) });
    } else {
      wx.removeTabBarBadge({ index: 2 });
    }
  } catch {
    /* 静默失败 */
  }
}
