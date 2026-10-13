/** 全部业务枚举字典：与后端 models 的字符串值一一对应 */

export type ItemType = "sell" | "give" | "swap" | "want";
export type ItemStatus = "on_sale" | "reserved" | "completed" | "archived" | "sunk";
export type WantStatus = "pending" | "accepted" | "rejected" | "done";
export type TradeStatus = "pending" | "arranged" | "completed" | "cancelled";
export type PlaceMethod = "face" | "porch" | "lobby";

export interface EnumMeta {
  value: string;
  label: string;
  /** CSS 变量形式的主题色，如 var(--ns-give) */
  color: string;
  desc?: string;
}

/* ---------------- 四形态 ---------------- */

export const ITEM_TYPE_MAP: Record<ItemType, EnumMeta> = {
  sell: { value: "sell", label: "出售", color: "var(--ns-sell)", desc: "标个参考价，等邻居来换" },
  give: { value: "give", label: "赠送", color: "var(--ns-give)", desc: "送给需要它的邻居" },
  swap: { value: "swap", label: "换物", color: "var(--ns-swap)", desc: "以物换物，各取所需" },
  want: { value: "want", label: "求购", color: "var(--ns-want)", desc: "说说你想要什么" },
};

export const ITEM_TYPES: EnumMeta[] = Object.values(ITEM_TYPE_MAP);

/* ---------------- 物品状态 ---------------- */

export const ITEM_STATUS_MAP: Record<ItemStatus, EnumMeta> = {
  on_sale: { value: "on_sale", label: "在架", color: "var(--ns-success)" },
  reserved: { value: "reserved", label: "已预约", color: "var(--ns-warning)" },
  completed: { value: "completed", label: "已完成", color: "var(--ns-ink-3)" },
  archived: { value: "archived", label: "已归档", color: "var(--ns-ink-3)" },
  sunk: { value: "sunk", label: "已沉底", color: "var(--ns-ink-3)" },
};

/* ---------------- 意向状态 ---------------- */

export const WANT_STATUS_MAP: Record<WantStatus, EnumMeta> = {
  pending: { value: "pending", label: "待回应", color: "var(--ns-warning)" },
  accepted: { value: "accepted", label: "已接受", color: "var(--ns-success)" },
  rejected: { value: "rejected", label: "已婉拒", color: "var(--ns-ink-3)" },
  done: { value: "done", label: "已完成", color: "var(--ns-ink-3)" },
};

/* ---------------- 交易状态 ---------------- */

export const TRADE_STATUS_MAP: Record<TradeStatus, EnumMeta> = {
  pending: { value: "pending", label: "待约定", color: "var(--ns-warning)" },
  arranged: { value: "arranged", label: "已约定", color: "var(--ns-swap)" },
  completed: { value: "completed", label: "已完成", color: "var(--ns-success)" },
  cancelled: { value: "cancelled", label: "已取消", color: "var(--ns-danger)" },
};

/* ---------------- 分类（9） ---------------- */

export const CATEGORY_MAP: Record<string, EnumMeta> = {
  baby: { value: "baby", label: "母婴", color: "var(--ns-give)" },
  book: { value: "book", label: "图书", color: "var(--ns-swap)" },
  appliance: { value: "appliance", label: "家电", color: "var(--ns-brand)" },
  furniture: { value: "furniture", label: "家具", color: "var(--ns-want)" },
  clothing: { value: "clothing", label: "服饰", color: "var(--ns-give)" },
  digital: { value: "digital", label: "数码", color: "var(--ns-swap)" },
  sports: { value: "sports", label: "运动", color: "var(--ns-success)" },
  kitchen: { value: "kitchen", label: "厨具", color: "var(--ns-warning)" },
  other: { value: "other", label: "其他", color: "var(--ns-ink-2)" },
};

export const CATEGORIES: EnumMeta[] = Object.values(CATEGORY_MAP);

/* ---------------- 成色（5） ---------------- */

export const CONDITION_MAP: Record<string, string> = {
  brand_new: "全新未拆",
  like_new: "99新",
  good: "9成新",
  used: "明显使用痕迹",
  worn: "功能正常有磨损",
};

export const CONDITIONS = Object.keys(CONDITION_MAP);

/* ---------------- 交接方式 ---------------- */

export const PLACE_METHOD_MAP: Record<PlaceMethod, { label: string; desc: string; icon: string }> = {
  face: { label: "当面见面", desc: "小区里碰头，当面验物", icon: "user" },
  porch: { label: "放门口自取", desc: "放在门口约定位置自取", icon: "gift" },
  lobby: { label: "物业前台", desc: "交到物业前台代为转交", icon: "shop" },
};

export const PLACE_METHODS = Object.keys(PLACE_METHOD_MAP) as PlaceMethod[];

/* ---------------- 通知类型（图标 + 颜色） ---------------- */

export const NOTIFY_META: Record<string, { icon: string; color: string }> = {
  want_received: { icon: "heart", color: "var(--ns-give)" },
  want_rejected: { icon: "error-circle", color: "var(--ns-ink-3)" },
  want_accepted: { icon: "check-circle", color: "var(--ns-success)" },
  item_message: { icon: "chat", color: "var(--ns-swap)" },
  chat_message: { icon: "chat", color: "var(--ns-swap)" },
  trade_arranged: { icon: "time", color: "var(--ns-want)" },
  trade_confirmed: { icon: "check-circle", color: "var(--ns-success)" },
  trade_completed: { icon: "check-circle", color: "var(--ns-brand)" },
  trade_cancelled: { icon: "error-circle", color: "var(--ns-danger)" },
  review_received: { icon: "star", color: "var(--ns-want)" },
  gratitude_received: { icon: "gift", color: "var(--ns-give)" },
  contact_exchanged: { icon: "user", color: "var(--ns-swap)" },
  item_sunk: { icon: "notification", color: "var(--ns-ink-2)" },
  system: { icon: "notification", color: "var(--ns-ink-2)" },
};

/** 通知兜底图标 */
export const NOTIFY_FALLBACK = { icon: "notification", color: "var(--ns-ink-2)" };
