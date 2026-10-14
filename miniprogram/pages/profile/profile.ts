import { get } from "../../services/api";
import { UserSummary } from "../../services/auth";
import { goodRate, tradesDone, relTime } from "../../utils/format";

interface ItemCardData {
  id: number;
  [k: string]: any;
}

Page({
  data: {
    loading: true,
    loadError: false,
    needJoin: false,
    user: null as UserSummary | null,
    items: [] as ItemCardData[],
    rate: "--",
    done: 0,
    joined: "",
  },

  id: 0,

  onLoad(query: Record<string, string>) {
    this.id = Number(query.id || 0);
    this.fetch();
  },

  async fetch() {
    this.setData({ loading: true, loadError: false });
    try {
      const r = await get<{ user: UserSummary; items: ItemCardData[] }>(`/api/users/${this.id}`);
      this.setData({
        loading: false,
        user: r.user,
        items: r.items || [],
        rate: goodRate(r.user.stats),
        done: tradesDone(r.user.stats),
        joined: relTime(r.user.created_at),
      });
    } catch (e: any) {
      this.setData({
        loading: false,
        loadError: true,
        needJoin: e && e.status === 403,
      });
    }
  },

  goVerify() {
    wx.navigateTo({ url: "/pages/verify/verify" });
  },

  onRetry() {
    this.fetch();
  },
});
