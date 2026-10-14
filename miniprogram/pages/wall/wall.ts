import { get, post, del, toastError } from "../../services/api";
import { Me, refreshMe } from "../../services/auth";

interface FaqRow {
  id: number;
  title: string;
  content: string;
  pinned: boolean;
  like_count: number;
  my_like: boolean;
  created_at: string;
}

Page({
  data: {
    items: [] as FaqRow[],
    finished: false,
    firstLoading: true,
    loadError: false,
    joined: true,
  },

  cursor: null as number | null,
  loadingMore: false,

  onLoad() {
    this.refresh();
  },

  onShow() {
    refreshMe().then((me: Me | null) => {
      if (me) this.setData({ joined: !!me.user.community_id || !!me.user.verified });
    });
  },

  refresh() {
    this.cursor = null;
    this.setData({ firstLoading: true, loadError: false, items: [] });
    this.loadPage();
  },

  async loadPage() {
    try {
      const params: Record<string, any> = { limit: 20 };
      if (this.cursor !== null) params.cursor = this.cursor;
      const r = await get<{ list: FaqRow[]; next_cursor: number | null }>("/api/faqs", params);
      this.cursor = r.next_cursor;
      this.setData({
        items: this.data.items.concat(r.list || []),
        finished: r.next_cursor === null,
        firstLoading: false,
      });
    } catch (e) {
      this.setData({ firstLoading: false, loadError: true });
    }
  },

  onReachBottom() {
    if (this.loadingMore || this.data.finished) return;
    this.loadingMore = true;
    this.loadPage().finally(() => {
      this.loadingMore = false;
    });
  },

  async onToggleLike(e: WechatMiniprogram.TouchEvent) {
    const { id, liked } = e.currentTarget.dataset as { id: number; liked: boolean };
    const idx = this.data.items.findIndex((x) => x.id === id);
    if (idx < 0) return;
    try {
      const r = liked
        ? await del<{ liked: boolean; like_count: number }>(`/api/faqs/${id}/like`)
        : await post<{ liked: boolean; like_count: number }>(`/api/faqs/${id}/like`);
      this.setData({
        [`items[${idx}].liked`]: r.liked,
        [`items[${idx}].like_count`]: r.like_count,
      });
    } catch (err) {
      toastError(err);
    }
  },

  onRetry() {
    this.refresh();
  },

  goVerify() {
    wx.navigateTo({ url: "/pages/verify/verify" });
  },

  onPullDownRefresh() {
    refreshMe();
    this.refresh();
    wx.stopPullDownRefresh();
  },
});
