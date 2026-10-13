import { CONFIG, LOCAL_DEV } from "./config/index";
import { ensureLogin, refreshUnreadBadge } from "./services/auth";

App({
  globalData: {},

  onLaunch() {
    if (!LOCAL_DEV) {
      // 云托管模式：初始化后所有请求走 callContainer，微信自动注入 X-WX-OPENID
      wx.cloud.init({ env: CONFIG.CLOUD_ENV, traceUser: true });
    }

    // 静默登录（后端按 openid 自动建档，无需注册）
    ensureLogin();

    // 版本更新提示
    const updater = wx.getUpdateManager();
    updater.onUpdateReady(() => {
      wx.showModal({
        title: "更新提示",
        content: "新版本已就绪，是否重启应用？",
        success: (res) => {
          if (res.confirm) updater.applyUpdate();
        },
      });
    });
  },

  onShow() {
    refreshUnreadBadge();
  },
});
