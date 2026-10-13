import { get, post, toastError } from "../../services/api";
import { refreshUnreadBadge } from "../../services/auth";
import { createListLoader, ListLoader } from "../../utils/list";
import { NOTIFY_META, NOTIFY_FALLBACK } from "../../utils/constants";
import { relTime } from "../../utils/format";
import { notificationTarget, navTo } from "../../utils/navigation";

interface NotificationRow {
  id: number;
  type: string;
  title: string;
  content: string;
  read: boolean;
  created_at: string;
  icon: string;
  color: string;
  timeText: string;
}

interface ConversationRow {
  id: number;
  item: { id: number; title: string; cover: string; type: string; status: string } | null;
  counterpart: { id: number; nickname: string; avatar_url: string; building: string };
  last_message: { content: string; created_at: string; sender_id: number } | null;
  updated_at: string;
  timeText: string;
}

Page({
  data: {
    tab: "notify" as "notify" | "chat",
    notifications: [] as NotificationRow[],
    notifyFinished: false,
    notifyLoading: false,
    conversations: [] as ConversationRow[],
  },

  loader: null as ListLoader<any> | null,

  onLoad() {
    this.initLoader();
  },

  onShow() {
    refreshUnreadBadge();
    this.loadConversations();
    if (this.loader) this.loader.refresh();
  },

  initLoader() {
    this.loader = createListLoader<any>({
      limit: 30,
      fetch: (cursor, limit) =>
        get<{ list: any[]; next_cursor: number | null }>("/api/notifications", {
          cursor: cursor === null ? undefined : cursor,
          limit,
        }),
      onUpdate: (state) => {
        const rows: NotificationRow[] = state.items.map((n) => {
          const meta = NOTIFY_META[n.type] || NOTIFY_FALLBACK;
          return {
            ...n,
            icon: meta.icon,
            color: meta.color,
            timeText: relTime(n.created_at),
          };
        });
        this.setData({ notifications: rows, notifyFinished: state.finished });
      },
      onError: () => wx.showToast({ title: "通知加载失败", icon: "none" }),
    });
  },

  async loadConversations() {
    try {
      const r = await get<{ list: any[] }>("/api/conversations");
      const rows: ConversationRow[] = (r.list || []).map((c) => ({
        ...c,
        timeText: relTime((c.last_message && c.last_message.created_at) || c.updated_at),
      }));
      this.setData({ conversations: rows });
    } catch {
      /* ignore */
    }
  },

  switchTab(e: WechatMiniprogram.TouchEvent) {
    this.setData({ tab: e.currentTarget.dataset.tab as "notify" | "chat" });
  },

  onNotifyTap(e: WechatMiniprogram.TouchEvent) {
    const idx = Number(e.currentTarget.dataset.index);
    const n = this.data.notifications[idx];
    if (!n) return;
    if (!n.read) {
      post("/api/notifications/read", { ids: [n.id] }).catch(() => {
        /* ignore */
      });
      this.setData({ [`notifications[${idx}].read`]: true });
    }
    const target = notificationTarget(n);
    if (target) navTo(target);
  },

  async onReadAll() {
    try {
      await post("/api/notifications/read-all");
      this.loader && this.loader.refresh();
      refreshUnreadBadge();
      wx.showToast({ title: "已全部标记", icon: "none" });
    } catch (e) {
      toastError(e);
    }
  },

  onConvTap(e: WechatMiniprogram.TouchEvent) {
    const id = e.currentTarget.dataset.id as number;
    wx.navigateTo({ url: `/pages/chat/chat?id=${id}` });
  },

  goHome() {
    wx.switchTab({ url: "/pages/home/home" });
  },

  onPullDownRefresh() {
    Promise.all([this.loader ? this.loader.refresh() : Promise.resolve(), this.loadConversations()])
      .finally(() => wx.stopPullDownRefresh());
  },

  onReachBottom() {
    if (this.data.tab === "notify" && this.loader) this.loader.loadMore();
  },
});
