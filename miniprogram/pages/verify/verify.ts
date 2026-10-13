import { get, post, toastError } from "../../services/api";
import { Me, refreshMe, setMe } from "../../services/auth";
import { chooseImages, uploadImage } from "../../services/upload";

Page({
  data: {
    me: null as Me | null,
    communityName: "",
    verifiedCount: 0,
    buildings: [] as string[],
    /* 码验证 */
    channel: "code" as "code" | "manual",
    code: "",
    codeSending: false,
    /* 人工审核 */
    manualBuilding: "",
    manualUnit: "",
    proofImage: "",
    manualUploading: false,
    manualSending: false,
    /* 担保码生成 */
    vouchCode: "",
    vouchExpires: "",
    vouchError: "",
  },

  onShow() {
    refreshMe().then((me) => {
      if (me) this.setData({ me });
    });
    this.loadCommunity();
  },

  async loadCommunity() {
    try {
      const r = await get<any>("/api/community/info");
      this.setData({
        communityName: r.name || "",
        verifiedCount: r.verified_count || 0,
        buildings: r.buildings || [],
      });
    } catch {
      /* ignore */
    }
  },

  switchChannel(e: WechatMiniprogram.TouchEvent) {
    this.setData({ channel: e.currentTarget.dataset.channel as "code" | "manual" });
  },

  /* ---------------- 邀请码 / 担保码 ---------------- */

  onCode(e: WechatMiniprogram.CustomEvent<{ value: string }>) {
    this.setData({ code: e.detail.value });
  },

  async onSubmitCode() {
    if (this.data.codeSending) return;
    const code = (this.data.code || "").trim().toUpperCase();
    if (!code) {
      wx.showToast({ title: "输入验证码", icon: "none" });
      return;
    }
    this.setData({ codeSending: true });
    try {
      const me = await post<Me>("/api/community/join", { code });
      setMe(me);
      wx.showToast({ title: "验证成功，欢迎回家", icon: "success" });
      setTimeout(() => wx.switchTab({ url: "/pages/home/home" }), 900);
    } catch (e) {
      this.setData({ codeSending: false });
      toastError(e);
    }
  },

  /* ---------------- 人工审核 ---------------- */

  onManualBuilding(e: WechatMiniprogram.CustomEvent<{ value: string }>) {
    this.setData({ manualBuilding: e.detail.value });
  },

  onManualBuildingPick(e: WechatMiniprogram.PickerChange) {
    this.setData({ manualBuilding: this.data.buildings[Number(e.detail.value)] || "" });
  },

  onManualUnit(e: WechatMiniprogram.CustomEvent<{ value: string }>) {
    this.setData({ manualUnit: e.detail.value });
  },

  async onPickProof() {
    if (this.data.manualUploading) return;
    try {
      const picked = await chooseImages(1);
      if (!picked.length) return;
      this.setData({ manualUploading: true });
      const url = await uploadImage(picked[0]);
      this.setData({ proofImage: url, manualUploading: false });
    } catch (e) {
      this.setData({ manualUploading: false });
      toastError(e);
    }
  },

  async onSubmitManual() {
    if (this.data.manualSending) return;
    if (!this.data.manualBuilding.trim()) {
      wx.showToast({ title: "填写楼栋", icon: "none" });
      return;
    }
    if (!this.data.proofImage) {
      wx.showToast({ title: "上传业主凭证照片", icon: "none" });
      return;
    }
    this.setData({ manualSending: true });
    try {
      await post("/api/community/manual-apply", {
        building: this.data.manualBuilding.trim(),
        unit: this.data.manualUnit.trim() || null,
        proof_image: this.data.proofImage,
      });
      wx.showToast({ title: "已提交，等待管理员审核", icon: "none", duration: 2200 });
      this.setData({ manualSending: false });
      const me = await refreshMe();
      if (me) this.setData({ me });
    } catch (e) {
      this.setData({ manualSending: false });
      toastError(e);
    }
  },

  /* ---------------- 老住户生成担保码 ---------------- */

  async onGenVouch() {
    try {
      const r = await post<{ code: string; expires_at: string }>("/api/community/vouch-invite");
      this.setData({ vouchCode: r.code, vouchError: "" });
    } catch (e: any) {
      this.setData({ vouchCode: "", vouchError: e && e.message ? e.message : "暂时无法生成担保码" });
    }
  },

  copyVouch() {
    if (!this.data.vouchCode) return;
    wx.setClipboardData({
      data: this.data.vouchCode,
      success: () => wx.showToast({ title: "担保码已复制", icon: "none" }),
    });
  },
});
