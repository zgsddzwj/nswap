import { get, toastError } from "../../services/api";
import { relTime } from "../../utils/format";
import { createListLoader, ListLoader } from "../../utils/list";

interface AnnouncementRow {
  id: number;
  title: string;
  content: string;
  created_at: string;
  timeText: string;
}

Page({
  data: {
    items: [] as AnnouncementRow[],
    finished: false,
    firstLoading: true,
  },

  loader: null as ListLoader<any> | null,

  onLoad() {
    this.loader = createListLoader<any>({
      limit: 20,
      fetch: (cursor, limit) =>
        get<{ list: any[]; next_cursor: number | null }>("/api/announcements", {
          cursor: cursor === null ? undefined : cursor,
          limit,
        }),
      onUpdate: (state) => {
        const rows: AnnouncementRow[] = state.items.map((a) => ({
          ...a,
          timeText: relTime(a.created_at),
        }));
        this.setData({ items: rows, finished: state.finished });
      },
      onError: () => wx.showToast({ title: "加载失败", icon: "none" }),
    });
    this.loader.refresh().then(() => this.setData({ firstLoading: false }));
  },

  onReachBottom() {
    if (this.loader) this.loader.loadMore();
  },

  goHome() {
    wx.switchTab({ url: "/pages/home/home" });
  },
});
