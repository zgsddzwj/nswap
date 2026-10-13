import { getMe, refreshMe, Me } from "../../services/auth";
import { ITEM_TYPES, EnumMeta, ItemType } from "../../utils/constants";

Page({
  data: {
    verified: true,
    types: [] as EnumMeta[],
  },

  onShow() {
    this.setData({ types: ITEM_TYPES });
    const cached = getMe();
    if (cached) {
      this.setData({ verified: !!cached.user.verified });
    }
    refreshMe().then((me: Me | null) => {
      if (me) this.setData({ verified: !!me.user.verified });
    });
  },

  onPick(e: WechatMiniprogram.TouchEvent) {
    const type = e.currentTarget.dataset.type as ItemType;
    if (!this.data.verified) {
      wx.showModal({
        title: "先完成小区验证",
        content: "仅限本小区已验证住户发布，去完成验证吧",
        confirmText: "去验证",
        success: (res) => {
          if (res.confirm) wx.navigateTo({ url: "/pages/verify/verify" });
        },
      });
      return;
    }
    wx.navigateTo({ url: `/pages/publish/edit/edit?type=${type}` });
  },
});
