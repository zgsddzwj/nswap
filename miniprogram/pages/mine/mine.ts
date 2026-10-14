import { put, get, post, toastError } from "../../services/api";
import { Me, getMe, refreshMe, setMe } from "../../services/auth";
import { setDevOpenid, devOpenid } from "../../services/api";
import { LOCAL_DEV, ADMIN_URL, DEV_IDENTITIES } from "../../config/index";
import { uploadImage } from "../../services/upload";
import { goodRate, tradesDone } from "../../utils/format";

interface ContactSettings {
  contact_enabled: boolean;
  contact_wechat: string;
  contact_phone: string;
}

Page({
  data: {
    me: null as Me | null,
    rate: "--",
    done: 0,
    isAdmin: false,
    localDev: LOCAL_DEV,
    identities: DEV_IDENTITIES,
    currentIdentity: "",
    adminUrl: ADMIN_URL,
    /* 资料编辑弹层 */
    showEdit: false,
    editNickname: "",
    editUnit: "",
    avatarTemp: "",
    saving: false,
    /* 联系方式设置（默认不开放，仅会话内限次交换） */
    showContact: false,
    contact: { contact_enabled: false, contact_wechat: "", contact_phone: "" } as ContactSettings,
    contactSaving: false,
  },

  onShow() {
    this.applyMe(getMe());
    refreshMe().then((me) => {
      if (me) this.applyMe(me);
    });
    if (LOCAL_DEV) this.setData({ currentIdentity: devOpenid() });
  },

  applyMe(me: Me | null) {
    if (!me) return;
    this.setData({
      me,
      rate: goodRate(me.user.stats),
      done: tradesDone(me.user.stats),
      isAdmin: me.user.role === "admin",
    });
  },

  /* ---------------- 资料编辑 ---------------- */

  openEdit() {
    const me = this.data.me!;
    this.setData({
      showEdit: true,
      editNickname: me.user.nickname,
      editUnit: me.user.unit || "",
      avatarTemp: "",
    });
  },

  closeEdit() {
    this.setData({ showEdit: false });
  },

  onVisibleChangeEdit(e: WechatMiniprogram.CustomEvent<{ visible: boolean }>) {
    if (e.detail.visible === false) this.setData({ showEdit: false });
  },

  onNickname(e: WechatMiniprogram.CustomEvent<{ value: string }>) {
    this.setData({ editNickname: e.detail.value });
  },

  onUnit(e: WechatMiniprogram.CustomEvent<{ value: string }>) {
    this.setData({ editUnit: e.detail.value });
  },

  async onChooseAvatar(e: WechatMiniprogram.CustomEvent<{ avatarUrl: string }>) {
    const url = e.detail.avatarUrl;
    if (url.startsWith("http")) {
      // 官方默认头像（完整 URL）直接可用
      this.setData({ avatarTemp: url });
      return;
    }
    // 本地临时文件：压缩上传
    try {
      wx.showLoading({ title: "上传头像中" });
      const remote = await uploadImage(url);
      this.setData({ avatarTemp: remote });
      wx.hideLoading();
    } catch (err) {
      wx.hideLoading();
      toastError(err);
    }
  },

  async onSaveProfile() {
    if (this.data.saving) return;
    const nickname = (this.data.editNickname || "").trim();
    if (!nickname) {
      wx.showToast({ title: "昵称不能为空", icon: "none" });
      return;
    }
    this.setData({ saving: true });
    try {
      const me = await put<Me>("/api/me", {
        nickname,
        unit: this.data.editUnit.trim() || null,
        avatar_url: this.data.avatarTemp || null,
      });
      setMe(me);
      this.setData({ showEdit: false, saving: false, me });
      wx.showToast({ title: "已保存", icon: "success" });
    } catch (e) {
      this.setData({ saving: false });
      toastError(e);
    }
  },

  /* ---------------- 联系方式设置 ---------------- */

  openContact() {
    this.setData({ showContact: true });
    get<ContactSettings>("/api/me/contact")
      .then((c) => this.setData({ contact: c }))
      .catch(() => {
        /* 保持默认空表单 */
      });
  },

  closeContact() {
    this.setData({ showContact: false });
  },

  onVisibleChangeContact(e: WechatMiniprogram.CustomEvent<{ visible: boolean }>) {
    if (e.detail.visible === false) this.setData({ showContact: false });
  },

  onContactEnabled(e: WechatMiniprogram.CustomEvent<{ value: boolean }>) {
    this.setData({ "contact.contact_enabled": e.detail.value });
  },

  onContactWechat(e: WechatMiniprogram.CustomEvent<{ value: string }>) {
    this.setData({ "contact.contact_wechat": e.detail.value });
  },

  onContactPhone(e: WechatMiniprogram.CustomEvent<{ value: string }>) {
    this.setData({ "contact.contact_phone": e.detail.value });
  },

  async onSaveContact() {
    if (this.data.contactSaving) return;
    const c = this.data.contact;
    if (c.contact_enabled && !c.contact_wechat.trim() && !c.contact_phone.trim()) {
      wx.showToast({ title: "开启前请至少填写一种联系方式", icon: "none" });
      return;
    }
    this.setData({ contactSaving: true });
    try {
      const saved = await put<ContactSettings>("/api/me/contact", {
        contact_enabled: c.contact_enabled,
        contact_wechat: c.contact_wechat.trim(),
        contact_phone: c.contact_phone.trim(),
      });
      this.setData({ contact: saved, showContact: false, contactSaving: false });
      wx.showToast({ title: "联系方式已保存", icon: "success" });
    } catch (e) {
      this.setData({ contactSaving: false });
      toastError(e);
    }
  },

  /* ---------------- 入口 ---------------- */

  goProfile() {
    const me = this.data.me;
    if (me) wx.navigateTo({ url: `/pages/profile/profile?id=${me.user.id}` });
  },

  go(e: WechatMiniprogram.TouchEvent) {
    wx.navigateTo({ url: e.currentTarget.dataset.url as string });
  },

  goVerify() {
    wx.navigateTo({ url: "/pages/verify/verify" });
  },

  goMyProfile() {
    const me = this.data.me;
    if (me) wx.navigateTo({ url: `/pages/profile/profile?id=${me.user.id}` });
  },

  copyAdmin() {
    wx.setClipboardData({
      data: this.data.adminUrl,
      success: () => wx.showToast({ title: "后台链接已复制，请在浏览器打开", icon: "none", duration: 2500 }),
    });
  },

  /* ---------------- 账号与隐私（注销，docs/09 P0-4） ---------------- */

  onDeleteAccount() {
    wx.showModal({
      title: "注销账号",
      content:
        "注销后：昵称与联系方式将被清除、在架物品下架、待处理意向取消；历史交易与评价记录将保留（展示为「已注销用户」）。此操作不可恢复。",
      confirmText: "继续注销",
      confirmColor: "#C9453B",
      success: (res) => {
        if (!res.confirm) return;
        // 二次确认：输入「注销」
        wx.showModal({
          title: "二次确认",
          content: "请输入「注销」两字确认",
          editable: true,
          placeholderText: "注销",
          success: async (r2) => {
            if (!r2.confirm) return;
            if ((r2.content || "").trim() !== "注销") {
              wx.showToast({ title: "输入不匹配，已取消", icon: "none" });
              return;
            }
            try {
              await post("/api/me/delete", { confirm: "注销" });
              wx.showToast({ title: "账号已注销", icon: "success" });
              wx.clearStorageSync();
              setTimeout(() => wx.reLaunch({ url: "/pages/home/home" }), 900);
            } catch (e) {
              toastError(e);
            }
          },
        });
      },
    });
  },

  /* ---------------- 开发者身份切换（仅本地） ---------------- */

  onIdentityChange(e: WechatMiniprogram.PickerChange) {
    const idx = Number(e.detail.value);
    const openid = this.data.identities[idx];
    setDevOpenid(openid);
    this.setData({ currentIdentity: openid });
    wx.showLoading({ title: "切换身份中" });
    // 重新登录并刷新全局状态
    wx.reLaunch({ url: "/pages/home/home" });
    setTimeout(() => wx.hideLoading(), 600);
  },
});
