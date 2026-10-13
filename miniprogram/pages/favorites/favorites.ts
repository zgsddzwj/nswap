import { get } from "../../services/api";
import { createListLoader, ListLoader } from "../../utils/list";

interface ItemCardData {
  id: number;
  [k: string]: any;
}

Page({
  data: {
    items: [] as ItemCardData[],
    finished: false,
    firstLoading: true,
  },

  loader: null as ListLoader<ItemCardData> | null,

  onLoad() {
    this.initLoader();
  },

  initLoader() {
    this.loader = createListLoader<ItemCardData>({
      limit: 20,
      fetch: (cursor, limit) =>
        get<{ list: ItemCardData[]; next_cursor: number | null }>("/api/favorites", {
          cursor: cursor === null ? undefined : cursor,
          limit,
        }),
      onUpdate: (state) => this.setData({ items: state.items, finished: state.finished }),
      onError: () => wx.showToast({ title: "加载失败", icon: "none" }),
    });
    this.loader.refresh().then(() => this.setData({ firstLoading: false }));
  },

  onPullDownRefresh() {
    this.initLoader();
    wx.stopPullDownRefresh();
  },

  onReachBottom() {
    if (this.loader) this.loader.loadMore();
  },

  goHome() {
    wx.switchTab({ url: "/pages/home/home" });
  },
});
