import { get, post, toastError, requestSubscribe } from "../../services/api";
import { UserSummary } from "../../services/auth";

const RATING_OPTIONS = [
  { value: 3, label: "满意", icon: "check-circle", desc: "顺利愉快" },
  { value: 2, label: "一般", icon: "info-circle", desc: "过程有点波折" },
  { value: 1, label: "不满意", icon: "error-circle", desc: "爽约或有纠纷" },
];

Page({
  data: {
    loading: true,
    t: null as any,
    counterpart: null as UserSummary | null,
    options: RATING_OPTIONS,
    rating: 0,
    content: "",
    submitting: false,
    /* 第二步：感谢帖（仅收受方） */
    step: "review" as "review" | "gratitude" | "done",
    gratitudeContent: "",
    toBuilding: "",
    gratSending: false,
  },

  id: 0,

  onLoad(query: Record<string, string>) {
    this.id = Number(query.id || 0);
  },

  onShow() {
    if (this.id) this.fetch();
  },

  async fetch() {
    try {
      const t = await get<any>(`/api/trades/${this.id}`);
      // 收受方：求购帖是物品方，其余是意向方
      const isReceiver = t.item
        ? t.item.type === "want"
          ? t.my_role === "owner"
          : t.my_role === "other"
        : false;
      const needGratitude = isReceiver && !t.gratitude && t.status === "completed";
      this.setData({
        loading: false,
        t,
        counterpart: t.counterpart,
        toBuilding: t.counterpart.building || "",
        step: t.my_review && needGratitude ? "gratitude" : t.my_review ? "done" : "review",
      });
    } catch (e) {
      this.setData({ loading: false });
      toastError(e);
    }
  },

  onPickRating(e: WechatMiniprogram.TouchEvent) {
    this.setData({ rating: Number(e.currentTarget.dataset.value) });
  },

  onContent(e: WechatMiniprogram.CustomEvent<{ value: string }>) {
    this.setData({ content: e.detail.value });
  },

  async onSubmitReview() {
    if (this.data.submitting) return;
    if (!this.data.rating) {
      wx.showToast({ title: "选一个评价", icon: "none" });
      return;
    }
    this.setData({ submitting: true });
    try {
      await post(`/api/trades/${this.id}/review`, {
        rating: this.data.rating,
        content: this.data.content.trim() || null,
      });
      wx.showToast({ title: "评价成功", icon: "success" });
      const needGratitude =
        this.data.t &&
        this.data.t.status === "completed" &&
        !this.data.t.gratitude &&
        this.isReceiverTrade();
      if (needGratitude) {
        this.setData({ step: "gratitude", submitting: false });
      } else {
        this.backToList();
      }
    } catch (e) {
      this.setData({ submitting: false });
      toastError(e);
    }
  },

  /** 当前用户是否为本交易收受方 */
  isReceiverTrade(): boolean {
    const t = this.data.t;
    if (!t || !t.item) return false;
    return t.item.type === "want" ? t.my_role === "owner" : t.my_role === "other";
  },

  onGratitude(e: WechatMiniprogram.CustomEvent<{ value: string }>) {
    this.setData({ gratitudeContent: e.detail.value });
  },

  async onSubmitGratitude() {
    if (this.data.gratSending) return;
    const content = (this.data.gratitudeContent || "").trim();
    if (!content) {
      wx.showToast({ title: "写一句感谢吧", icon: "none" });
      return;
    }
    this.setData({ gratSending: true });
    try {
      await post(`/api/trades/${this.id}/gratitude`, {
        content,
        to_building: this.data.toBuilding || null,
      });
      wx.showToast({ title: "感谢帖已发布", icon: "success" });
      this.backToList();
    } catch (e) {
      this.setData({ gratSending: false });
      toastError(e);
    }
  },

  onSkipGratitude() {
    this.backToList();
  },

  backToList() {
    wx.redirectTo({ url: "/pages/my-trades/my-trades" });
  },
});
