import { put, toastError } from "../../services/api";
import { Me, getMe, refreshMe, setMe } from "../../services/auth";
import { setDevOpenid, devOpenid } from "../../services/api";
import { LOCAL_DEV, ADMIN_URL, DEV_IDENTITIES } from "../../config/index";
import { uploadImage } from "../../services/upload";
import { goodRate, tradesDone } from "../../utils/format";

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
