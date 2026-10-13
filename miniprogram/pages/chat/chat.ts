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

const POLL_INTERVAL = 5000;

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
    this.timer = setInterval(() => this.pullNew(), POLL_INTERVAL);
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
    if (!this.convId || !this.lastId) return;
    try {
      const r = await get<{ list: any[] }>(`/api/conversations/${this.convId}/messages`, {
        since: this.lastId,
      });
      if (r.list && r.list.length) {
        this.applyMessages(r.list, false);
        refreshUnreadBadge();
      }
    } catch {
      /* 轮询失败静默，下个周期重试 */
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
});
