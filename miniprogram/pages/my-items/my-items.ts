import { get, post, del, toastError } from "../../services/api";
import { createListLoader, ListLoader } from "../../utils/list";

interface ItemRow {
  id: number;
  title: string;
  status: string;
  cover: string | null;
  view_count: number;
  want_count: number;
  [k: string]: any;
}

const TABS = [
  { value: "on_sale", label: "在架" },
  { value: "reserved", label: "已预约" },
  { value: "sunk", label: "已沉底" },
  { value: "completed", label: "已完成" },
  { value: "archived", label: "已归档" },
];

Page({
  data: {
    tabs: TABS,
    tab: "on_sale",
    items: [] as ItemRow[],
    finished: false,
    firstLoading: true,
  },

  loader: null as ListLoader<ItemRow> | null,

  onLoad() {
    this.initLoader();
  },

  initLoader() {
    this.loader = createListLoader<ItemRow>({
      limit: 20,
      fetch: (cursor, limit) =>
        get<{ list: ItemRow[]; next_cursor: string | null }>("/api/items", {
          mine: true,
          status: this.data.tab,
          cursor: cursor || undefined,
          limit,
        }),
      onUpdate: (state) => this.setData({ items: state.items, finished: state.finished }),
      onError: (e) => toastError(e),
    });
    this.loader.refresh().then(() => this.setData({ firstLoading: false }));
  },

  onTab(e: WechatMiniprogram.TouchEvent) {
    const tab = e.currentTarget.dataset.value as string;
    if (tab === this.data.tab) return;
    this.setData({ tab, firstLoading: true });
    this.initLoader();
  },

  actionsFor(item: ItemRow): string[] {
    const actions: string[] = [];
    if (item.status === "on_sale" || item.status === "sunk") actions.push("编辑");
    if (item.status === "on_sale" || item.status === "sunk") actions.push("续期");
    if (item.status === "on_sale" || item.status === "sunk") actions.push("下架");
    if (item.status !== "reserved") actions.push("删除");
    return actions;
  },

  onManage(e: WechatMiniprogram.TouchEvent) {
    const id = e.currentTarget.dataset.id as number;
    const item = this.data.items.find((x) => x.id === id);
    if (!item) return;
    const actions = this.actionsFor(item);
    if (!actions.length) {
      wx.showToast({ title: "当前状态不可操作", icon: "none" });
      return;
    }
    wx.showActionSheet({
      itemList: actions,
      success: (res) => {
        const action = actions[res.tapIndex];
        if (action === "编辑") {
          wx.navigateTo({ url: `/pages/publish/edit/edit?id=${id}` });
        } else if (action === "续期") {
          this.renew(id);
        } else if (action === "下架") {
          this.offShelf(id);
        } else if (action === "删除") {
          this.remove(id);
        }
      },
    });
  },

  async renew(id: number) {
    try {
      await post(`/api/items/${id}/renew`);
      wx.showToast({ title: "已续期，重新亮相", icon: "success" });
      this.initLoader();
    } catch (e) {
      toastError(e);
    }
  },

  offShelf(id: number) {
    wx.showModal({
      title: "下架物品",
      content: "下架后将归档，不再出现在社区列表",
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await post(`/api/items/${id}/off-shelf`);
          wx.showToast({ title: "已下架", icon: "success" });
          this.initLoader();
        } catch (e) {
          toastError(e);
        }
      },
    });
  },

  remove(id: number) {
    wx.showModal({
      title: "删除物品",
      content: "删除后不可恢复，确定删除吗？",
      confirmColor: "#C9453B",
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await del(`/api/items/${id}`);
          wx.showToast({ title: "已删除", icon: "success" });
          this.initLoader();
        } catch (e) {
          toastError(e);
        }
      },
    });
  },

  goPublish() {
    wx.switchTab({ url: "/pages/publish/publish" });
  },

  onRetry() {
    this.setData({ firstLoading: true });
    this.initLoader();
  },
});
