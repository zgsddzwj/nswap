import { get } from "../../services/api";
import { Me, getMe, refreshMe, refreshUnreadBadge, redirectIfNotVerified } from "../../services/auth";
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

interface Announcement {
  id: number;
  title: string;
  content: string;
  created_at: string;
}

interface ItemCardData {
  id: number;
  type: string;
  title: string;
  cover: string | null;
  status: string;
  building: string;
  community_name: string;
  [k: string]: any;
}

type Scope = "community" | "city";

Page({
  data: {
    me: null as Me | null,
    verified: true,
    joined: true, // 是否已加入小区（verified 即已加入）
    scope: "community" as Scope,
    announcement: null as Announcement | null,
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
      const joined = !!me.user.community_id || !!me.user.verified;
      const scope: Scope = joined ? this.data.scope : "city";
      this.setData({ me, verified: !!me.user.verified, joined, scope });
      if (me.community && me.community.name) {
        wx.setNavigationBarTitle({ title: me.community.name });
      }
      if (joined) {
        this.loadAnnouncements();
        if (!this.data.buildings.length) this.loadBuildings();
      } else {
        this.setData({ announcement: null, buildings: [] });
      }
      this.refreshItems();
    });
    refreshUnreadBadge();
  },

  initLoader() {
    this.loader = createListLoader<ItemCardData>({
      limit: 20,
      fetch: (cursor, limit) => {
        const f = this.data.filters;
        const params: Record<string, any> = { limit, scope: this.data.scope };
        if (cursor) params.cursor = cursor;
        if (f.type) params.type = f.type as ItemType;
        if (f.category) params.category = f.category;
        // 楼栋筛选仅本小区模式有意义
        if (f.building && this.data.scope === "community") params.building = f.building;
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
  },

  refreshItems() {
    this.setData({ firstLoading: true, loadError: false });
    this.loader!.refresh().then(() => this.setData({ firstLoading: false }));
  },

  async loadAnnouncements() {
    try {
      const r = await get<{ list: Announcement[] }>("/api/announcements", { limit: 1 });
      this.setData({ announcement: (r.list || [])[0] || null });
    } catch {
      this.setData({ announcement: null });
    }
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

  onScopeTap(e: WechatMiniprogram.TouchEvent) {
    const scope = e.currentTarget.dataset.scope as Scope;
    if (scope === this.data.scope) return;
    this.setData({ scope });
    this.refreshItems();
  },

  goAnnouncements() {
    wx.navigateTo({ url: "/pages/announcements/announcements" });
  },

  onFiltersChange(e: WechatMiniprogram.CustomEvent<{ type: string; category: string; building: string }>) {
    this.setData({ filters: e.detail });
    this.refreshItems();
  },

  goSearch() {
    wx.navigateTo({ url: "/pages/search/search" });
  },

  goVerify() {
    wx.navigateTo({ url: "/pages/verify/verify" });
  },

  goWall() {
    wx.navigateTo({ url: "/pages/wall/wall" });
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
      this.data.joined ? this.loadAnnouncements() : Promise.resolve(),
      refreshMe().then((me) => {
        if (me) {
          const joined = !!me.user.community_id || !!me.user.verified;
          this.setData({ me, verified: !!me.user.verified, joined });
        }
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
    this.refreshItems();
  },

  onShareAppMessage() {
    const me = getMe();
    return {
      title: me && me.community ? `来${me.community.name}交换闲置吧` : "邻里闲置交换",
      path: "/pages/home/home",
    };
  },
});
