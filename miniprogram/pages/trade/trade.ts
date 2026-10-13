import { get, put, toastError, requestSubscribe } from "../../services/api";
import { UserSummary } from "../../services/auth";
import { TRADE_STATUS_MAP, PLACE_METHODS, PLACE_METHOD_MAP, PlaceMethod } from "../../utils/constants";
import { formatDateTime, toIso, splitPrice, goodRate } from "../../utils/format";
interface Trade {
  id: number;
  status: string;
  item: { id: number; title: string; cover: string; type: string; status: string } | null;
  counterpart: UserSummary;
  my_role: "owner" | "other";
  want: { message: string; bid_cents: number | null; swap_offer: string | null } | null;
  place_method: PlaceMethod | null;
  meet_time: string | null;
  place_note: string | null;
  owner_confirmed: boolean;
  other_confirmed: boolean;
  my_confirmed: boolean;
  cancel_reason: string | null;
  reviews: { from_user_id: number; rating: number; content: string }[];
  my_review: { rating: number; content: string | null } | null;
  gratitude: { content: string } | null;
  created_at: string;
  completed_at: string | null;
  [k: string]: any;
}

Page({
  data: {
    loading: true,
    t: null as Trade | null,
    statusLabel: "",
    statusColor: "",
    cancelled: false,
    stepIndex: 0,
    meetTimeText: "",
    placeMethods: PLACE_METHODS,
    placeMethodMap: PLACE_METHOD_MAP,
    placeMethod: "" as PlaceMethod | "",
    date: "",
    time: "",
    placeNote: "",
    canArrange: false,
    canConfirm: false,
    canCancel: false,
    isReceiver: false,
    bidInt: "",
    cpRate: "--",
    reviewLabels: ["", "不满意", "一般", "满意"],
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
      const t = await get<Trade>(`/api/trades/${this.id}`);
      const today = new Date();
      const pad = (n: number) => (n < 10 ? `0${n}` : String(n));
      const defaultDate = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;
      // 收受方：求购帖是物品方，其余是意向方
      const isReceiver = t.item
        ? t.item.type === "want"
          ? t.my_role === "owner"
          : t.my_role === "other"
        : false;
      this.setData({
        loading: false,
        t,
        statusLabel: TRADE_STATUS_MAP[t.status as keyof typeof TRADE_STATUS_MAP]?.label || t.status,
        statusColor: TRADE_STATUS_MAP[t.status as keyof typeof TRADE_STATUS_MAP]?.color || "",
        cancelled: t.status === "cancelled",
        stepIndex: t.status === "pending" ? 0 : t.status === "arranged" ? 1 : t.status === "completed" ? 2 : -1,
        meetTimeText: t.meet_time ? formatDateTime(t.meet_time) : "",
        placeMethod: t.place_method || "",
        date: t.meet_time ? t.meet_time.slice(0, 10) : defaultDate,
        time: t.meet_time ? t.meet_time.slice(11, 16) : "",
        placeNote: t.place_note || "",
        canArrange: t.status === "pending" || t.status === "arranged",
        canConfirm: (t.status === "pending" || t.status === "arranged") && !t.my_confirmed,
        canCancel: t.status === "pending" || t.status === "arranged",
        isReceiver,
        bidInt: t.want && t.want.bid_cents ? splitPrice(t.want.bid_cents).int : "",
        cpRate: goodRate(t.counterpart.stats),
      });
    } catch (e) {
      this.setData({ loading: false });
      toastError(e);
    }
  },

  onPickMethod(e: WechatMiniprogram.TouchEvent) {
    const method = e.currentTarget.dataset.method as PlaceMethod;
    // 跨小区仅允许当面（后端同样校验，docs/07 §4.5）
    if (this.data.t && this.data.t.cross_community && method !== "face") {
      wx.showToast({ title: "跨小区交换请选择当面交接", icon: "none" });
      return;
    }
    this.setData({ placeMethod: method });
  },

  onDate(e: WechatMiniprogram.PickerChange) {
    this.setData({ date: String(e.detail.value) });
  },

  onTime(e: WechatMiniprogram.PickerChange) {
    this.setData({ time: String(e.detail.value) });
  },

  onNote(e: WechatMiniprogram.CustomEvent<{ value: string }>) {
    this.setData({ placeNote: e.detail.value });
  },

  async onSaveArrange() {
    const { placeMethod, date, time, placeNote } = this.data;
    if (!placeMethod) {
      wx.showToast({ title: "选一种交接方式", icon: "none" });
      return;
    }
    if (!date || !time) {
      wx.showToast({ title: "约一个交接时间", icon: "none" });
      return;
    }
    try {
      await put(`/api/trades/${this.id}/arrange`, {
        place_method: placeMethod,
        meet_time: toIso(new Date(`${date}T${time}`)),
        place_note: placeNote.trim() || null,
      });
      wx.showToast({ title: "已保存，对方会收到通知", icon: "none" });
      this.fetch();
    } catch (e) {
      toastError(e);
    }
  },

  async onConfirm() {
    const res = await wx.showModal({
      title: "确认完成交换",
      content: "双方都确认后交易完结。请确保已当面完成交接",
    });
    if (!res.confirm) return;
    await requestSubscribe(["confirm", "review"]);
    try {
      const t = await put<Trade>(`/api/trades/${this.id}/confirm`);
      if (t.status === "completed") {
        wx.showModal({
          title: "交换完成 🎉",
          content: "花 5 秒给邻居一个评价吧",
          confirmText: "去评价",
          cancelText: "稍后",
          success: (r) => {
            if (r.confirm) wx.redirectTo({ url: `/pages/review/review?id=${this.id}` });
            else this.fetch();
          },
        });
      } else {
        wx.showToast({ title: "已确认，等待对方", icon: "none" });
        this.fetch();
      }
    } catch (e) {
      toastError(e);
    }
  },

  async onCancel() {
    const res = await wx.showModal({
      title: "取消交易",
      content: "取消会记录在你的信用档案中，物品将重新上架",
      editable: true,
      placeholderText: "取消原因（选填）",
    });
    if (!res.confirm) return;
    try {
      await put(`/api/trades/${this.id}/cancel`, { reason: res.content || "" });
      wx.showToast({ title: "已取消", icon: "none" });
      this.fetch();
    } catch (e) {
      toastError(e);
    }
  },

  goItem() {
    const t = this.data.t;
    if (t && t.item) wx.navigateTo({ url: `/pages/detail/detail?id=${t.item.id}` });
  },

  goCounterpart() {
    const t = this.data.t;
    if (t) wx.navigateTo({ url: `/pages/profile/profile?id=${t.counterpart.id}` });
  },

  goReview() {
    wx.redirectTo({ url: `/pages/review/review?id=${this.id}` });
  },

  goMyTrades() {
    wx.redirectTo({ url: "/pages/my-trades/my-trades" });
  },
});
