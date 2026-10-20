import { get, post, toastError } from "../../services/api";
import { refreshUnreadBadge } from "../../services/auth";
import { relTime } from "../../utils/format";

interface ChatMessage {
  id: number;
  sender_id: number;
  content: string;
  created_at: string;
  mine?: boolean;
  showTime?: boolean;
  timeText?: string;
}

interface ContactStatus {
  exchanged: boolean;
  remaining_today: number;
  counterpart: { id: number; nickname: string; building: string };
  contact: { wechat: string | null; phone: string | null } | null;
}

const POLL_INTERVAL = 5000;
const POLL_INTERVAL_SLOW = 15000; // 连续失败后降频（docs/09 P1-11）
const POLL_FAIL_THRESHOLD = 3;

Page({
  data: {
    convId: 0,
    item: null as { id: number; title: string; cover: string; type: string; status: string } | null,
    counterpart: null as any,
    messages: [] as ChatMessage[],
    input: "",
    loading: true,
    sending: false,
    tradeId: 0,
    scrollInto: "",
    /* 联系方式交换 */
    contact: null as ContactStatus | null,
    showContactSheet: false,
    exchanging: false,
    pollFails: 0,
  },

  convId: 0,
  myId: 0,
  lastId: 0,
  timer: 0 as unknown as ReturnType<typeof setInterval> | 0,
  tradeId: 0,

  onLoad(query: Record<string, string>) {
    this.convId = Number(query.id || 0);
    this.tradeId = Number(query.tradeId || 0);
    this.setData({ convId: this.convId });
    this.bootstrap();
  },

  onShow() {
    if (this.convId) this.startPolling();
  },

  onHide() {
    this.stopPolling();
  },

  onUnload() {
    this.stopPolling();
  },

  stopPolling() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = 0;
    }
  },

  startPolling() {
    this.stopPolling();
    const interval =
      this.data.pollFails >= POLL_FAIL_THRESHOLD ? POLL_INTERVAL_SLOW : POLL_INTERVAL;
    this.timer = setInterval(() => this.pullNew(), interval);
  },

  async bootstrap() {
    try {
      // 会话无单独详情接口：从列表中找本会话
      const [convs, me] = await Promise.all([
        get<{ list: any[] }>("/api/conversations"),
        get<any>("/api/me"),
      ]);
      this.myId = me.user.id;
      const conv = (convs.list || []).find((c) => c.id === this.convId);
      if (conv) {
        wx.setNavigationBarTitle({ title: conv.counterpart.nickname });
        this.setData({ item: conv.item, counterpart: conv.counterpart });
        if (conv.item) wx.setNavigationBarTitle({ title: conv.counterpart.nickname });
      }
      // 首屏消息
      const r = await get<{ list: any[] }>(`/api/conversations/${this.convId}/messages`);
      this.applyMessages(r.list || [], true);
      this.setData({ loading: false });
      this.loadContactStatus();
      if (!this.tradeId) this.lookupTrade();
      this.startPolling();
    } catch (e) {
      this.setData({ loading: false });
      toastError(e);
    }
  },

  async lookupTrade() {
    try {
      // 找与本会话物品匹配的交易（先进行中，再已完成的最近一笔）
      for (const status of ["ongoing", "completed"]) {
        const r = await get<{ list: any[] }>("/api/trades", { status, limit: 50 });
        const t = (r.list || []).find(
          (x) =>
            x.item &&
            this.data.item &&
            x.item.id === this.data.item.id &&
            x.counterpart.id === this.data.counterpart.id
        );
        if (t) {
          this.setData({ tradeId: t.id });
          return;
        }
      }
    } catch {
      /* 去约定按钮隐藏即可 */
    }
  },

  applyMessages(list: any[], reset: boolean) {
    const mapped: ChatMessage[] = list.map((m) => ({
      ...m,
      mine: m.sender_id === this.myId,
      timeText: relTime(m.created_at),
    }));
    // 相邻消息间隔超过 10 分钟显示时间
    const base = reset ? [] : this.data.messages;
    const all = reset ? mapped : base.concat(mapped);
    for (let i = 0; i < all.length; i++) {
      if (i === 0) {
        all[i].showTime = true;
        continue;
      }
      const prev = new Date(all[i - 1].created_at).getTime();
      const cur = new Date(all[i].created_at).getTime();
      all[i].showTime = isNaN(cur) || cur - prev > 10 * 60 * 1000;
    }
    if (all.length) this.lastId = all[all.length - 1].id;
    this.setData({
      messages: all,
      scrollInto: all.length ? `msg-${all[all.length - 1].id}` : "",
    });
  },

  async pullNew() {
    // 注意：lastId=0（空会话）是合法状态——对方首条消息必须能拉到；
    // 只需保证会话已确定，不可用 !lastId 拦截（否则空会话轮询死锁）
    if (!this.convId) return;
    try {
      const r = await get<{ list: any[] }>(`/api/conversations/${this.convId}/messages`, {
        since: this.lastId,
      });
      if (r.list && r.list.length) {
        this.applyMessages(r.list, false);
        refreshUnreadBadge();
      }
      if (this.data.pollFails) {
        // 网络恢复：复位轮询频率
        this.setData({ pollFails: 0 });
        this.startPolling();
      }
    } catch {
      const fails = this.data.pollFails + 1;
      this.setData({ pollFails: fails });
      if (fails === POLL_FAIL_THRESHOLD) this.startPolling(); // 降频
    }
  },

  onInput(e: WechatMiniprogram.CustomEvent<{ value: string }>) {
    this.setData({ input: e.detail.value });
  },

  async onSend() {
    const content = (this.data.input || "").trim();
    if (!content || this.data.sending) return;
    this.setData({ sending: true });
    try {
      const m = await post<any>(`/api/conversations/${this.convId}/messages`, { content });
      this.applyMessages([m], false);
      this.setData({ input: "", sending: false });
    } catch (e) {
      this.setData({ sending: false });
      toastError(e);
    }
  },

  goItem() {
    if (this.data.item) {
      wx.navigateTo({ url: `/pages/detail/detail?id=${this.data.item.id}` });
    }
  },

  goTrade() {
    if (this.data.tradeId) {
      wx.navigateTo({ url: `/pages/trade/trade?id=${this.data.tradeId}` });
    }
  },

  /* ---------------- 联系方式交换 ---------------- */

  async loadContactStatus() {
    try {
      const c = await get<ContactStatus>(`/api/conversations/${this.convId}/contact`);
      this.setData({ contact: c });
    } catch {
      /* 状态加载失败不影响聊天 */
    }
  },

  openContactSheet() {
    this.setData({ showContactSheet: true });
  },

  closeContactSheet() {
    this.setData({ showContactSheet: false });
  },

  onVisibleChangeContact(e: WechatMiniprogram.CustomEvent<{ visible: boolean }>) {
    if (e.detail.visible === false) this.setData({ showContactSheet: false });
  },

  async doExchange() {
    if (this.data.exchanging) return;
    this.setData({ exchanging: true });
    try {
      const c = await post<ContactStatus>(`/api/conversations/${this.convId}/contact`);
      this.setData({ contact: c, showContactSheet: false, exchanging: false });
      wx.showToast({ title: "已交换，注意隐私安全", icon: "none", duration: 2200 });
    } catch (e) {
      this.setData({ showContactSheet: false, exchanging: false });
      toastError(e);
    }
  },

  onCopyContact(e: WechatMiniprogram.TouchEvent) {
    const value = e.currentTarget.dataset.value as string;
    if (!value) return;
    wx.setClipboardData({
      data: value,
      success: () => wx.showToast({ title: "已复制", icon: "none" }),
    });
  },
});
