import { get } from "../../services/api";
import { createListLoader, ListLoader } from "../../utils/list";
import { relTime } from "../../utils/format";

interface TradeRow {
  id: number;
  status: string;
  item: { id: number; title: string; cover: string; type: string; status: string } | null;
  counterpart: { id: number; nickname: string; building: string; avatar_url: string };
  created_at: string;
  timeText: string;
}

const TABS = [
  { value: "ongoing", label: "进行中" },
  { value: "completed", label: "已完成" },
  { value: "cancelled", label: "已取消" },
];

Page({
  data: {
    tabs: TABS,
    tab: "ongoing",
    trades: [] as TradeRow[],
    finished: false,
    firstLoading: true,
  },

  loader: null as ListLoader<any> | null,

  onLoad() {
    this.initLoader();
  },

  initLoader() {
    // 注意：后端 /api/trades 不传 status 会返回空列表（已知实现行为），必须显式传
    this.loader = createListLoader<any>({
      limit: 20,
      fetch: (cursor, limit) =>
        get<{ list: any[]; next_cursor: number | null }>("/api/trades", {
          status: this.data.tab,
          cursor: cursor === null ? undefined : cursor,
          limit,
        }),
      onUpdate: (state) => {
        const rows: TradeRow[] = state.items.map((t) => ({
          ...t,
          timeText: relTime(t.created_at),
        }));
        this.setData({ trades: rows, finished: state.finished });
      },
      onError: () => wx.showToast({ title: "加载失败", icon: "none" }),
    });
    this.loader.refresh().then(() => this.setData({ firstLoading: false }));
  },

  onTab(e: WechatMiniprogram.TouchEvent) {
    const tab = e.currentTarget.dataset.value as string;
    if (tab === this.data.tab) return;
    this.setData({ tab, firstLoading: true });
    this.initLoader();
  },

  goTrade(e: WechatMiniprogram.TouchEvent) {
    const id = e.currentTarget.dataset.id as number;
    wx.navigateTo({ url: `/pages/trade/trade?id=${id}` });
  },

  goHome() {
    wx.switchTab({ url: "/pages/home/home" });
  },

  onPullDownRefresh() {
    this.initLoader();
    wx.stopPullDownRefresh();
  },

  onReachBottom() {
    if (this.loader) this.loader.loadMore();
  },
});
