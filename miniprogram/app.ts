import { CONFIG, LOCAL_DEV, TERMS_VERSION } from "./config/index";
import { ensureLogin, refreshUnreadBadge } from "./services/auth";
import { post } from "./services/api";

App({
  globalData: {},

  onLaunch() {
    if (!LOCAL_DEV) {
      // 云托管模式：初始化后所有请求走 callContainer，微信自动注入 X-WX-OPENID
      wx.cloud.init({ env: CONFIG.CLOUD_ENV, traceUser: true });
    }

    // 静默登录（后端按 openid 自动建档，无需注册）；成功后检查协议同意状态
    ensureLogin().then((me) => {
      if (!me) return;
      if ((me.user.agreed_terms_version || "") !== TERMS_VERSION) {
        wx.showModal({
          title: "用户协议与隐私政策",
          content:
            "欢迎使用邻里闲置交换。我们仅收集必要信息（微信标识、昵称头像、楼栋单元），不采集定位、不强制手机号；平台不介入资金往来，请当面验货。继续使用即表示你已阅读并同意《用户协议》与《隐私政策》。",
          confirmText: "同意并继续",
          cancelText: "不同意",
          success: (res) => {
            if (res.confirm) {
              post("/api/me/agree", { version: TERMS_VERSION }).catch(() => {
                /* 记录失败不阻塞使用，下次启动重试 */
              });
            } else {
              wx.exitMiniProgram();
            }
          },
        });
      }
    });

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
