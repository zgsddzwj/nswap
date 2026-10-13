import { get } from "../../services/api";
import { Me, getMe, refreshMe, refreshUnreadBadge } from "../../services/auth";
import { createListLoader, ListLoader } from "../../utils/list";
import { ItemType } from "../../utils/constants";

interface Gratitude {
  id: number;
  content: string;
  to_building: string | null;
  user: { nickname: string; building: string };
  item_id: number | null;
  created_at: string;
}

interface ItemCardData {
  id: number;
  type: string;
  title: string;
  cover: string | null;
  status: string;
  [k: string]: any;
}

Page({
  data: {
    me: null as Me | null,
    verified: true,
    gratitudes: [] as Gratitude[],
    buildings: [] as string[],
    filters: { type: "", category: "", building: "" },
    items: [] as ItemCardData[],
    finished: false,
    firstLoading: true,
    loadError: false,
    footerText: "",
  },

  loader: null as ListLoader<ItemCardData> | null,

  onLoad() {
    this.initLoader();
    this.loadGratitudes();
  },

  onShow() {
    refreshMe().then((me) => {
      if (!me) return;
      this.setData({ me, verified: !!me.user.verified });
      if (me.community && me.community.name) {
        wx.setNavigationBarTitle({ title: me.community.name });
      }
      if (me.user.verified && !this.data.buildings.length) this.loadBuildings();
    });
    refreshUnreadBadge();
  },

  initLoader() {
    this.loader = createListLoader<ItemCardData>({
      limit: 20,
      fetch: (cursor, limit) => {
        const f = this.data.filters;
        const params: Record<string, any> = { limit };
        if (cursor) params.cursor = cursor;
        if (f.type) params.type = f.type as ItemType;
        if (f.category) params.category = f.category;
        if (f.building) params.building = f.building;
        return get<{ list: ItemCardData[]; next_cursor: string | null }>("/api/items", params);
      },
      onUpdate: (state) => {
        this.setData({
          items: state.items,
          finished: state.finished,
          footerText: state.finished ? (state.items.length ? "没有更多了" : "") : "",
        });
      },
      onError: () => this.setData({ loadError: true }),
    });
    // 触发首屏
    this.loader.refresh().then(() => this.setData({ firstLoading: false }));
  },

  async loadGratitudes() {
    try {
      const r = await get<{ list: Gratitude[] }>("/api/gratitudes", { limit: 10 });
      this.setData({ gratitudes: r.list || [] });
    } catch {
      /* 首屏非关键数据，静默 */
    }
  },

  async loadBuildings() {
    try {
      const r = await get<{ buildings: string[] }>("/api/community/info");
      this.setData({ buildings: r.buildings || [] });
    } catch {
      /* ignore */
    }
  },

  onFiltersChange(e: WechatMiniprogram.CustomEvent<{ type: string; category: string; building: string }>) {
    this.setData({ filters: e.detail, firstLoading: true, loadError: false });
    this.loader!.refresh().then(() => this.setData({ firstLoading: false }));
  },

  goSearch() {
    wx.navigateTo({ url: "/pages/search/search" });
  },

  goVerify() {
    wx.navigateTo({ url: "/pages/verify/verify" });
  },

  onEmptyAction() {
    if (this.data.verified) {
      wx.switchTab({ url: "/pages/publish/publish" });
    } else {
      this.goVerify();
    }
  },

  goGratitude(e: WechatMiniprogram.TouchEvent) {
    const id = e.currentTarget.dataset.itemId as number | null;
    if (id) wx.navigateTo({ url: `/pages/detail/detail?id=${id}` });
  },

  onPullDownRefresh() {
    Promise.all([
      this.loader!.refresh(),
      this.loadGratitudes(),
      refreshMe().then((me) => {
        if (me) this.setData({ me, verified: !!me.user.verified });
      }),
    ]).finally(() => {
      this.setData({ firstLoading: false });
      wx.stopPullDownRefresh();
    });
  },

  onReachBottom() {
    this.loader!.loadMore();
  },

  onRetry() {
    this.setData({ firstLoading: true, loadError: false });
    this.loader!.refresh().then(() => this.setData({ firstLoading: false }));
  },

  onShareAppMessage() {
    const me = getMe();
    return {
      title: me && me.community ? `来${me.community.name}交换闲置吧` : "邻里闲置交换",
      path: "/pages/home/home",
    };
  },
});
