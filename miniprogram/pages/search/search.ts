import { get } from "../../services/api";
import { createListLoader, ListLoader } from "../../utils/list";

interface ItemCardData {
  id: number;
  [k: string]: any;
}

const HISTORY_KEY = "ns_search_history";

Page({
  data: {
    keyword: "",
    searched: false,
    history: [] as string[],
    items: [] as ItemCardData[],
    finished: false,
    firstLoading: false,
  },

  loader: null as ListLoader<ItemCardData> | null,

  onLoad() {
    this.setData({ history: wx.getStorageSync(HISTORY_KEY) || [] });
  },

  initLoader(keyword: string) {
    this.loader = createListLoader<ItemCardData>({
      limit: 20,
      fetch: (cursor, limit) =>
        get<{ list: ItemCardData[]; next_cursor: string | null }>("/api/items", {
          keyword,
          cursor: cursor || undefined,
          limit,
        }),
      onUpdate: (state) => this.setData({ items: state.items, finished: state.finished }),
      onError: () => wx.showToast({ title: "搜索失败，请重试", icon: "none" }),
    });
  },

  onInput(e: WechatMiniprogram.CustomEvent<{ value: string }>) {
    this.setData({ keyword: e.detail.value });
  },

  onConfirm() {
    this.doSearch(this.data.keyword);
  },

  onHistoryTap(e: WechatMiniprogram.TouchEvent) {
    const kw = e.currentTarget.dataset.kw as string;
    this.setData({ keyword: kw });
    this.doSearch(kw);
  },

  onClearHistory() {
    wx.removeStorageSync(HISTORY_KEY);
    this.setData({ history: [] });
  },

  async doSearch(keyword: string) {
    const kw = (keyword || "").trim();
    if (!kw) {
      wx.showToast({ title: "输入想找的东西", icon: "none" });
      return;
    }
    // 历史记录去重置顶，最多 10 条
    const history = [kw].concat(
      (this.data.history as string[]).filter((h) => h !== kw)
    ).slice(0, 10);
    wx.setStorageSync(HISTORY_KEY, history);
    this.setData({ history, searched: true, firstLoading: true });
    this.initLoader(kw);
    await this.loader!.refresh();
    this.setData({ firstLoading: false });
  },

  onReachBottom() {
    if (this.loader) this.loader.loadMore();
  },
});
