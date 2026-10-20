import { yuanToCents } from "../../utils/format";

/**
 * 提交意向弹层。
 * - sell + negotiable：可附「小刀价」
 * - swap：可附「我用 XX 换」提议
 */
Component({
  // 允许 app.wxss 的全局设计系统类（ns-btn 等）在组件内生效：
  // 否则提交按钮无背景色、文字不居中（默认 isolated 会隔离掉全局类）
  options: { styleIsolation: "apply-shared" },
  properties: {
    show: { type: Boolean, value: false },
    itemType: { type: String, value: "sell" },
    negotiable: { type: Boolean, value: false },
  },

  data: {
    message: "",
    bidYuan: "",
    swapOffer: "",
    sending: false,
  },

  observers: {
    show(this: any, show: boolean) {
      if (show) {
        this.setData({ message: "", bidYuan: "", swapOffer: "", sending: false });
      }
    },
  },

  methods: {
    onClose(this: any) {
      this.triggerEvent("close");
    },
    onVisibleChange(this: any, e: WechatMiniprogram.CustomEvent<{ visible: boolean }>) {
      if (e.detail.visible === false) this.triggerEvent("close");
    },
    onMessage(this: any, e: WechatMiniprogram.CustomEvent<{ value: string }>) {
      this.setData({ message: e.detail.value });
    },
    onBid(this: any, e: WechatMiniprogram.CustomEvent<{ value: string }>) {
      this.setData({ bidYuan: e.detail.value });
    },
    onSwapOffer(this: any, e: WechatMiniprogram.CustomEvent<{ value: string }>) {
      this.setData({ swapOffer: e.detail.value });
    },
    onSubmit(this: any) {
      if (this.data.sending) return;
      const message = (this.data.message || "").trim();
      if (!message) {
        wx.showToast({ title: "说点什么吧，让邻居更安心", icon: "none" });
        return;
      }
      let bid_cents: number | null = null;
      if (this.data.itemType === "sell" && this.data.negotiable && this.data.bidYuan.trim()) {
        bid_cents = yuanToCents(this.data.bidYuan);
        if (bid_cents === null) {
          wx.showToast({ title: "出价格式不对，如 12.5", icon: "none" });
          return;
        }
      }
      const swap_offer =
        this.data.itemType === "swap" && this.data.swapOffer.trim()
          ? this.data.swapOffer.trim()
          : null;
      this.setData({ sending: true });
      this.triggerEvent("submit", { message, bid_cents, swap_offer });
      // sending 状态由 show 的 observer 在关闭后重置
      setTimeout(() => this.setData({ sending: false }), 1200);
    },
  },
});
