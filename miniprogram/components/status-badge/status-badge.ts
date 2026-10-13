import { ITEM_STATUS_MAP, WANT_STATUS_MAP, TRADE_STATUS_MAP, EnumMeta } from "../../utils/constants";

const MAPS: Record<string, Record<string, EnumMeta>> = {
  item: ITEM_STATUS_MAP,
  want: WANT_STATUS_MAP,
  trade: TRADE_STATUS_MAP,
};

Component({
  properties: {
    /** 字典域：item | want | trade */
    kind: { type: String, value: "item" },
    status: { type: String, value: "" },
  },

  data: {
    label: "",
    color: "var(--ns-ink-3)",
  },

  observers: {
    "kind, status"(this: any, kind: string, status: string) {
      const map = MAPS[kind] || MAPS.item;
      const meta = map[status];
      this.setData({
        label: meta ? meta.label : status,
        color: meta ? meta.color : "var(--ns-ink-3)",
      });
    },
  },
});
