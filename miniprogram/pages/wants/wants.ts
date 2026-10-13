import { get, put, toastError, requestSubscribe } from "../../services/api";
import { UserSummary } from "../../services/auth";
import { splitPrice, relTime, goodRate, tradesDone } from "../../utils/format";
import { WANT_STATUS_MAP } from "../../utils/constants";

interface WantItem {
  id: number;
  message: string;
  bid_cents: number | null;
  swap_offer: string | null;
  status: string;
  created_at: string;
  user: UserSummary;
  [k: string]: any;
}

Page({
  data: {
    loading: true,
    item: null as any,
    wants: [] as WantItem[],
  },

  itemId: 0,

  onLoad(query: Record<string, string>) {
    this.itemId = Number(query.itemId || 0);
  },

  onShow() {
    this.fetch();
  },

  async fetch() {
    this.setData({ loading: true });
    try {
      const [detail, wants] = await Promise.all([
        get<any>(`/api/items/${this.itemId}`),
        get<{ list: WantItem[] }>(`/api/items/${this.itemId}/wants`),
      ]);
      const list = (wants.list || []).map((w) => ({
        ...w,
        priceInt: splitPrice(w.bid_cents).int,
        timeText: relTime(w.created_at),
        statusLabel: WANT_STATUS_MAP[w.status as keyof typeof WANT_STATUS_MAP]?.label || w.status,
        statusColor: WANT_STATUS_MAP[w.status as keyof typeof WANT_STATUS_MAP]?.color || "var(--ns-ink-3)",
        userRate: goodRate(w.user.stats),
        userDone: tradesDone(w.user.stats),
      }));
      this.setData({ loading: false, item: detail, wants: list });
    } catch (e) {
      this.setData({ loading: false });
      toastError(e);
    }
  },

  onAccept(e: WechatMiniprogram.TouchEvent) {
    const id = e.currentTarget.dataset.id as number;
    wx.showModal({
      title: "接受这位邻居？",
      content: "接受后将建立会话并进入约定环节，其余意向自动失效",
      success: async (res) => {
        if (!res.confirm) return;
        await requestSubscribe(["want"]);
        try {
          const r = await put<{ trade_id: number; conversation_id: number }>(`/api/wants/${id}`, {
            action: "accept",
          });
          wx.showToast({ title: "已接受", icon: "success" });
          wx.redirectTo({ url: `/pages/chat/chat?id=${r.conversation_id}&tradeId=${r.trade_id}` });
        } catch (e) {
          toastError(e);
        }
      },
    });
  },

  onReject(e: WechatMiniprogram.TouchEvent) {
    const id = e.currentTarget.dataset.id as number;
    wx.showModal({
      title: "婉拒这位邻居？",
      content: "婉拒后 TA 仍可重新提交意向",
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await put(`/api/wants/${id}`, { action: "reject" });
          wx.showToast({ title: "已婉拒", icon: "none" });
          this.fetch();
        } catch (e) {
          toastError(e);
        }
      },
    });
  },

  goItem() {
    wx.navigateTo({ url: `/pages/detail/detail?id=${this.itemId}` });
  },
});
