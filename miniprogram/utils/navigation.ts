/** 通知 → 目标页 的路由映射（按后端 payload 字段跳转） */

export interface NotificationLike {
  type: string;
  payload?: Record<string, any>;
}

export function notificationTarget(n: NotificationLike): string | null {
  const p = n.payload || {};
  switch (n.type) {
    case "want_received":
      return p.item_id ? `/pages/wants/wants?itemId=${p.item_id}` : null;
    case "want_rejected":
    case "item_message":
    case "item_sunk":
      return p.item_id ? `/pages/detail/detail?id=${p.item_id}` : null;
    case "want_accepted":
    case "trade_arranged":
    case "trade_confirmed":
    case "trade_completed":
    case "trade_cancelled":
    case "review_received":
    case "gratitude_received":
      return p.trade_id ? `/pages/trade/trade?id=${p.trade_id}` : null;
    case "chat_message":
      return p.conversation_id ? `/pages/chat/chat?id=${p.conversation_id}` : null;
    default:
      return null;
  }
}

export function navTo(url: string) {
  if (!url) return;
  wx.navigateTo({
    url,
    fail: () => {
      // 目标页是 tabBar 页时 navigateTo 会失败，降级 switchTab
      wx.switchTab({ url: url.split("?")[0] });
    },
  });
}
