import { ITEM_TYPE_MAP, CATEGORY_MAP, CONDITION_MAP, ItemType } from "../../utils/constants";
import { splitPrice, relTime } from "../../utils/format";

interface ItemCard {
  id: number;
  type: string;
  title: string;
  price_cents: number | null;
  negotiable?: boolean;
  condition?: string | null;
  building: string;
  status: string;
  cover: string | null;
  created_at: string;
  last_active_at?: string;
}

function buildCard(item: ItemCard) {
  const typeMeta = ITEM_TYPE_MAP[item.type as ItemType] || ITEM_TYPE_MAP.sell;
  const price = splitPrice(item.price_cents);
  const dimmed = item.status === "completed" || item.status === "archived" || item.status === "sunk";
  const showStatus = item.status && item.status !== "on_sale";
  const parts: string[] = [];
  if (item.building) parts.push(item.building);
  if (item.condition && CONDITION_MAP[item.condition]) parts.push(CONDITION_MAP[item.condition]);
  const time = relTime(item.last_active_at || item.created_at);
  if (time) parts.push(time);
  return {
    typeMeta,
    priceInt: price.int,
    priceDec: price.dec,
    showPrice: item.type === "sell" && item.price_cents !== null && item.price_cents !== undefined,
    showGive: item.type === "give",
    showSwap: item.type === "swap",
    showWant: item.type === "want",
    showStatus,
    dimmed,
    metaText: parts.join(" · "),
  };
}

Component({
  properties: {
    item: { type: Object },
    /** grid：双列网格卡；row：横向管理行（可带操作 slot） */
    mode: { type: String, value: "grid" },
  },

  data: buildCard({} as ItemCard),

  observers: {
    item(this: any, item: ItemCard) {
      if (!item) return;
      this.setData(buildCard(item));
    },
  },

  methods: {
    goDetail(this: any) {
      const item = this.data.item as ItemCard;
      if (!item) return;
      wx.navigateTo({ url: `/pages/detail/detail?id=${item.id}` });
    },
  },
});
