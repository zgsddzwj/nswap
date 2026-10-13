import { get, post, del, toastError, requestSubscribe } from "../../services/api";
import { getMe, refreshMe } from "../../services/auth";
import { CONDITION_MAP, ITEM_TYPE_MAP, ItemType } from "../../utils/constants";
import { splitPrice, relTime, goodRate, tradesDone } from "../../utils/format";

interface ItemDetail {
  id: number;
  type: ItemType;
  title: string;
  price_cents: number | null;
  negotiable: boolean;
  category: string;
  condition: string | null;
  building: string;
  status: string;
  cover: string | null;
  want_count: number;
  view_count: number;
  created_at: string;
  last_active_at: string;
  is_mine: boolean;
  description: string;
  want_desc: string | null;
  bid_cents: number | null;
  images: string[];
  message_count: number;
  seller: any;
  is_favorite: boolean;
  my_want: { id: number; status: string } | null;
  can_want: boolean;
  can_want_reason: string;
  active_trade_id: number | null;
  [k: string]: any;
}

interface MessageItem {
  id: number;
  content: string;
  created_at: string;
  user: { id: number; nickname: string; avatar_url: string; building: string };
}

const REPORT_REASONS = ["禁售物品", "涉嫌虚假", "内容违规", "其他"];

Page({  data: {
    loading: true,
    loadError: false,
    d: null as ItemDetail | null,
    typeMeta: ITEM_TYPE_MAP.sell,
    priceInt: "0",
    priceDec: "",
    conditionLabel: "",
    timeText: "",
    sellerRate: "--",
    sellerDone: 0,
    /* 底栏 */
    footerMode: "guest" as
      | "guest" | "want" | "pending" | "accepted" | "reserved"
      | "mine_onsale" | "mine_sunk" | "mine_ongoing" | "mine_done" | "archived",
    footerLabel: "",
    footerReason: "",
    favBusy: false,
    /* 留言 */
    messages: [] as MessageItem[],
    messageInput: "",
    msgCursor: null as number | null,
    msgFinished: true,
    /* 意向弹层 */
    showWantSheet: false,
    /* 举报弹层 */
    showReport: false,
    reportReason: "",
    reportDetail: "",
    reportSending: false,
  },

  id: 0,
  msgCursorValue: null as number | null,

  onLoad(query: Record<string, string>) {
    this.id = Number(query.id || 0);
    this.fetchDetail();
  },

  onShow() {
    // 从 want-sheet/trade 返回时刷新状态（浏览量等）
    if (!this.data.loading && this.id) {
      refreshMe();
      this.fetchDetail(true);
    }
  },

  async fetchDetail(silent = false) {
    if (!silent) this.setData({ loading: true, loadError: false });
    try {
      const d = await get<ItemDetail>(`/api/items/${this.id}`);
      this.applyDetail(d);
      this.setData({ loading: false });
      this.loadMessages(true);
    } catch (e) {
      this.setData({ loading: false, loadError: true });
    }
  },

  applyDetail(d: ItemDetail) {
    const price = splitPrice(d.price_cents);
    const footer = this.computeFooter(d);
    this.setData({
      d,
      typeMeta: ITEM_TYPE_MAP[d.type] || ITEM_TYPE_MAP.sell,
      priceInt: price.int,
      priceDec: price.dec,
      conditionLabel: d.condition ? CONDITION_MAP[d.condition] || "" : "",
      timeText: relTime(d.created_at),
      sellerRate: d.seller ? goodRate(d.seller.stats) : "--",
      sellerDone: d.seller ? tradesDone(d.seller.stats) : 0,
      ...footer,
    });
  },

  computeFooter(d: ItemDetail) {
    if (d.is_mine) {
      if (d.status === "on_sale") {
        return { footerMode: "mine_onsale", footerLabel: `查看意向${d.want_count ? `（${d.want_count}）` : ""}`, footerReason: "" };
      }
      if (d.status === "sunk") {
        return { footerMode: "mine_sunk", footerLabel: "一键续期", footerReason: "沉底后可免费续期，回到列表前排" };
      }
      if (d.status === "reserved" || d.status === "completed") {
        return {
          footerMode: "mine_ongoing",
          footerLabel: d.active_trade_id ? "查看交易" : "查看意向",
          footerReason: "",
        };
      }
      return { footerMode: "archived", footerLabel: "已归档", footerReason: "物品已下架归档" };
    }
    if (d.active_trade_id) {
      return { footerMode: "reserved", footerLabel: "查看交易", footerReason: "" };
    }
    if (d.my_want && d.my_want.status === "pending") {
      return { footerMode: "pending", footerLabel: "意向已提交", footerReason: "等待卖家回应，可撤回后重新提交" };
    }
    if (d.my_want && d.my_want.status === "accepted") {
      return { footerMode: "accepted", footerLabel: "和 TA 聊聊", footerReason: "" };
    }
    if (d.can_want) {
      return { footerMode: "want", footerLabel: d.type === "want" ? "我可以提供" : "我想要", footerReason: "" };
    }
    return { footerMode: "guest", footerLabel: d.type === "want" ? "我可以提供" : "我想要", footerReason: d.can_want_reason || "暂无法提交意向" };
  },

  /* ---------------- 底栏动作 ---------------- */

  onFooterTap() {
    const { footerMode, d } = this.data as { footerMode: string; d: ItemDetail };
    switch (footerMode) {
      case "mine_onsale":
        wx.navigateTo({ url: `/pages/wants/wants?itemId=${d.id}` });
        break;
      case "mine_sunk":
        this.onRenew();
        break;
      case "mine_ongoing":
        if (d.active_trade_id) {
          wx.navigateTo({ url: `/pages/trade/trade?id=${d.active_trade_id}` });
        } else {
          wx.navigateTo({ url: `/pages/wants/wants?itemId=${d.id}` });
        }
        break;
      case "reserved":
        wx.navigateTo({ url: `/pages/trade/trade?id=${d.active_trade_id}` });
        break;
      case "accepted":
        this.goChat();
        break;
      case "want":
        this.setData({ showWantSheet: true });
        break;
      case "pending":
        this.confirmWithdraw();
        break;
      default:
        if (this.data.footerReason) wx.showToast({ title: this.data.footerReason, icon: "none" });
    }
  },

  async onRenew() {
    try {
      await post(`/api/items/${this.id}/renew`);
      wx.showToast({ title: "已续期，重新亮相", icon: "success" });
      this.fetchDetail(true);
    } catch (e) {
      toastError(e);
    }
  },

  async confirmWithdraw() {
    const want = this.data.d!.my_want!;
    const res = await wx.showModal({
      title: "撤回意向",
      content: "撤回后可以重新提交意向",
    });
    if (!res.confirm) return;
    try {
      await del(`/api/wants/${want.id}`);
      wx.showToast({ title: "已撤回", icon: "none" });
      this.fetchDetail(true);
    } catch (e) {
      toastError(e);
    }
  },

  async goChat() {
    // 会话无单独详情接口，从会话列表按物品匹配
    try {
      const r = await get<{ list: any[] }>("/api/conversations");
      const conv = (r.list || []).find((c) => c.item && c.item.id === this.data.d!.id);
      if (conv) {
        wx.navigateTo({ url: `/pages/chat/chat?id=${conv.id}` });
      } else {
        wx.showToast({ title: "会话已建立，稍后在消息页查看", icon: "none" });
      }
    } catch (e) {
      toastError(e);
    }
  },

  /* ---------------- 收藏 ---------------- */

  async onToggleFav() {
    if (this.data.favBusy) return;
    const d = this.data.d!;
    this.setData({ favBusy: true });
    try {
      if (d.is_favorite) {
        await del(`/api/items/${d.id}/favorite`);
      } else {
        await post(`/api/items/${d.id}/favorite`);
      }
      this.setData({
        favBusy: false,
        "d.is_favorite": !d.is_favorite,
      });
      wx.showToast({ title: d.is_favorite ? "已取消收藏" : "已收藏", icon: "none" });
    } catch (e) {
      this.setData({ favBusy: false });
      toastError(e);
    }
  },

  /* ---------------- 意向 ---------------- */

  onWantSheetClose() {
    this.setData({ showWantSheet: false });
  },

  async onWantSubmit(e: WechatMiniprogram.CustomEvent<{ message: string; bid_cents: number | null; swap_offer: string | null }>) {
    const { message, bid_cents, swap_offer } = e.detail;
    await requestSubscribe(["accepted"]);
    try {
      await post(`/api/items/${this.id}/wants`, { message, bid_cents, swap_offer });
      this.setData({ showWantSheet: false });
      wx.showToast({ title: "已通知卖家，请等待回应", icon: "none", duration: 2200 });
      this.fetchDetail(true);
    } catch (err) {
      this.setData({ showWantSheet: false });
      toastError(err);
    }
  },

  /* ---------------- 我的物品管理 ---------------- */

  onEdit() {
    wx.navigateTo({ url: `/pages/publish/edit/edit?id=${this.id}` });
  },

  onOffShelf() {
    wx.showModal({
      title: "下架物品",
      content: "下架后将归档，不再出现在社区列表",
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await post(`/api/items/${this.id}/off-shelf`);
          wx.showToast({ title: "已下架", icon: "success" });
          this.fetchDetail(true);
        } catch (e) {
          toastError(e);
        }
      },
    });
  },

  onDelete() {
    wx.showModal({
      title: "删除物品",
      content: "删除后不可恢复，确定删除吗？",
      confirmColor: "#C9453B",
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await del(`/api/items/${this.id}`);
          wx.showToast({ title: "已删除", icon: "success" });
          setTimeout(() => wx.navigateBack(), 600);
        } catch (e) {
          toastError(e);
        }
      },
    });
  },

  onMineMenu() {
    const d = this.data.d!;
    const items: string[] = ["编辑"];
    if (d.status === "on_sale" || d.status === "sunk") items.push("下架");
    items.push("删除");
    wx.showActionSheet({
      itemList: items,
      success: (res) => {
        const action = items[res.tapIndex];
        if (action === "编辑") this.onEdit();
        else if (action === "下架") this.onOffShelf();
        else if (action === "删除") this.onDelete();
      },
    });
  },

  /* ---------------- 留言板 ---------------- */

  async loadMessages(reset = false) {
    try {
      const params: Record<string, any> = { limit: 30 };
      if (!reset && this.msgCursorValue !== null) params.cursor = this.msgCursorValue;
      const r = await get<{ list: MessageItem[]; next_cursor: number | null }>(
        `/api/items/${this.id}/messages`,
        params
      );
      const list = r.list || [];
      this.msgCursorValue = r.next_cursor;
      this.setData({
        messages: reset ? list : this.data.messages.concat(list),
        msgCursor: r.next_cursor,
        msgFinished: r.next_cursor === null,
      });
    } catch {
      /* 留言板加载失败不打断主页面 */
    }
  },

  onMoreMessages() {
    this.loadMessages(false);
  },

  onMessageInput(e: WechatMiniprogram.CustomEvent<{ value: string }>) {
    this.setData({ messageInput: e.detail.value });
  },

  async onSendMessage() {
    const content = (this.data.messageInput || "").trim();
    if (!content) return;
    const me = getMe();
    if (!me || !me.user.verified) {
      wx.showToast({ title: "完成小区验证后才能留言", icon: "none" });
      return;
    }
    try {
      const msg = await post<MessageItem>(`/api/items/${this.id}/messages`, { content });
      this.setData({
        messages: this.data.messages.concat(msg),
        messageInput: "",
      });
    } catch (e) {
      toastError(e);
    }
  },

  /* ---------------- 举报 ---------------- */

  onOpenReport() {
    this.setData({ showReport: true, reportReason: "", reportDetail: "" });
  },

  onCloseReport() {
    this.setData({ showReport: false });
  },

  onVisibleChangeReport(e: WechatMiniprogram.CustomEvent<{ visible: boolean }>) {
    if (e.detail.visible === false) this.setData({ showReport: false });
  },

  onPickReportReason(e: WechatMiniprogram.TouchEvent) {
    this.setData({ reportReason: e.currentTarget.dataset.reason as string });
  },

  onReportDetail(e: WechatMiniprogram.CustomEvent<{ value: string }>) {
    this.setData({ reportDetail: e.detail.value });
  },

  async onSubmitReport() {
    if (this.data.reportSending) return;
    if (!this.data.reportReason) {
      wx.showToast({ title: "请选择举报原因", icon: "none" });
      return;
    }
    this.setData({ reportSending: true });
    try {
      await post("/api/reports", {
        target_type: "item",
        target_id: this.id,
        reason: this.data.reportReason,
        detail: this.data.reportDetail || null,
      });
      this.setData({ showReport: false, reportSending: false });
      wx.showToast({ title: "已提交，我们会尽快处理", icon: "none" });
    } catch (e) {
      this.setData({ reportSending: false });
      toastError(e);
    }
  },

  /* ---------------- 其他 ---------------- */

  goSeller() {
    const d = this.data.d!;
    wx.navigateTo({ url: `/pages/profile/profile?id=${d.seller.id}` });
  },

  onPreviewImage(e: WechatMiniprogram.TouchEvent) {
    const current = e.currentTarget.dataset.src as string;
    const urls = this.data.d!.images;
    wx.previewImage({ current, urls });
  },

  onRetry() {
    this.fetchDetail();
  },

  goBack() {
    wx.navigateBack({
      fail: () => wx.switchTab({ url: "/pages/home/home" }),
    });
  },

  onShareAppMessage() {
    const d = this.data.d;
    return {
      title: d ? d.title : "邻里闲置交换",
      path: d ? `/pages/detail/detail?id=${d.id}` : "/pages/home/home",
    };
  },
});
