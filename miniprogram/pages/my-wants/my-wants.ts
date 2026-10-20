/** 我的意向：我提交过的所有意向与状态（待回应/已接受/已完成/未通过），可撤回待回应的意向 */
import { del, get, toastError } from "../../services/api";
import { relTime } from "../../utils/format";

const CHIPS = [
  { key: "", label: "全部" },
  { key: "pending", label: "待回应" },
  { key: "accepted", label: "已接受" },
  { key: "done", label: "已完成" },
  { key: "rejected", label: "未通过" },
];

const STATUS_TEXT: Record<string, string> = {
  pending: "待回应",
  accepted: "已接受",
  done: "已完成",
  rejected: "未通过",
};

interface WantRow {
  id: number;
  status: string;
  message: string;
  bid_cents: number | null;
  swap_offer: string | null;
  created_at: string;
  item: { id: number; title: string; cover: string | null } | null;
  statusText: string;
  timeText: string;
  swapOffer: string;
}

Page({
  data: {
    chips: CHIPS,
    filter: "",
    rows: [] as WantRow[],
    loading: true,
  },

  onLoad() {
    this.fetch();
  },

  async fetch(): Promise<void> {
    this.setData({ loading: true });
    try {
      const qs = this.data.filter ? `?status=${this.data.filter}&limit=50` : "?limit=50";
      const r = await get<{ list: any[] }>(`/api/me/wants${qs}`);
      const rows: WantRow[] = (r.list || []).map((w) => ({
        ...w,
        statusText: STATUS_TEXT[w.status] || w.status,
        timeText: relTime(w.created_at),
        swapOffer: w.swap_offer || "",
      }));
      this.setData({ rows, loading: false });
    } catch (e) {
      this.setData({ loading: false });
      toastError(e);
    }
  },

  onChip(e: WechatMiniprogram.TouchEvent) {
    const key = e.currentTarget.dataset.key as string;
    if (key === this.data.filter) return;
    this.setData({ filter: key });
    this.fetch();
  },

  goDetail(e: WechatMiniprogram.TouchEvent) {
    const id = e.currentTarget.dataset.id as number;
    if (id) wx.navigateTo({ url: `/pages/detail/detail?id=${id}` });
  },

  async onWithdraw(e: WechatMiniprogram.TouchEvent) {
    const id = e.currentTarget.dataset.id as number;
    const res = await wx.showModal({
      title: "撤回意向",
      content: "撤回后可以重新提交意向",
    });
    if (!res.confirm) return;
    try {
      await del(`/api/wants/${id}`);
      wx.showToast({ title: "已撤回", icon: "none" });
      this.fetch();
    } catch (err) {
      toastError(err);
    }
  },

  goHome() {
    wx.switchTab({ url: "/pages/home/home" });
  },

  async onPullDownRefresh() {
    await this.fetch();
    wx.stopPullDownRefresh();
  },
});
