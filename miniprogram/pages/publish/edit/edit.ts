import { get, post, put, toastError } from "../../../services/api";
import {
  ITEM_TYPE_MAP,
  CONDITION_MAP,
  CONDITIONS,
  ItemType,
} from "../../../utils/constants";
import { yuanToCents, splitPrice } from "../../../utils/format";
import { chooseImages, uploadImages } from "../../../services/upload";

const MAX_IMAGES = 9;

interface EditableDetail {
  id: number;
  type: ItemType;
  title: string;
  description: string;
  category: string;
  condition: string | null;
  price_cents: number | null;
  negotiable: boolean;
  want_desc: string | null;
  bid_cents: number | null;
  images: string[];
  status: string;
  is_mine: boolean;
}

Page({
  data: {
    type: "sell" as ItemType,
    typeMeta: ITEM_TYPE_MAP.sell,
    editId: 0,
    /* 表单 */
    images: [] as string[],
    title: "",
    description: "",
    condition: "",
    priceYuan: "",
    bidYuan: "",
    negotiable: false,
    wantDesc: "",
    conditions: CONDITIONS,
    conditionLabels: CONDITION_MAP,
    /* 上传/提交状态 */
    uploading: false,
    uploadProgress: "",
    submitting: false,
  },

  onLoad(query: Record<string, string>) {
    const type = (query.type || "sell") as ItemType;
    this.setData({
      type,
      typeMeta: ITEM_TYPE_MAP[type] || ITEM_TYPE_MAP.sell,
      editId: Number(query.id || 0),
    });
    wx.setNavigationBarTitle({
      title: query.id ? "编辑闲置" : ITEM_TYPE_MAP[type] ? `发布·${ITEM_TYPE_MAP[type].label}` : "发布闲置",
    });
    if (query.id) this.loadForEdit(Number(query.id));
  },

  async loadForEdit(id: number) {
    try {
      const d = await get<EditableDetail>(`/api/items/${id}`);
      if (!d.is_mine || (d.status !== "on_sale" && d.status !== "sunk")) {
        wx.showToast({ title: "当前状态不可编辑", icon: "none" });
        setTimeout(() => wx.navigateBack(), 800);
        return;
      }
      const price = splitPrice(d.price_cents);
      this.setData({
        images: d.images || [],
        title: d.title,
        description: d.description || "",
        condition: d.condition || "",
        priceYuan: price.dec ? `${price.int}${price.dec}` : price.int,
        bidYuan: d.bid_cents ? String(d.bid_cents / 100) : "",
        negotiable: !!d.negotiable,
        wantDesc: d.want_desc || "",
      });
    } catch (e) {
      toastError(e);
      setTimeout(() => wx.navigateBack(), 800);
    }
  },

  /* ---------------- 图片 ---------------- */

  async onAddImage() {
    if (this.data.uploading) return;
    try {
      const picked = await chooseImages(MAX_IMAGES - this.data.images.length);
      if (!picked.length) return;
      this.setData({ uploading: true, uploadProgress: `0/${picked.length}` });
      const urls = await uploadImages(picked, (done, total) => {
        this.setData({ uploadProgress: `${done}/${total}` });
      });
      this.setData({ images: this.data.images.concat(urls), uploading: false });
    } catch (e: any) {
      this.setData({ uploading: false });
      toastError(e);
    }
  },

  onDeleteImage(e: WechatMiniprogram.TouchEvent) {
    const idx = e.currentTarget.dataset.index as number;
    const images = this.data.images.slice();
    images.splice(idx, 1);
    this.setData({ images });
  },

  onPreviewImage(e: WechatMiniprogram.TouchEvent) {
    const current = e.currentTarget.dataset.src as string;
    wx.previewImage({ current, urls: this.data.images });
  },

  /* ---------------- 字段 ---------------- */

  onTitle(e: WechatMiniprogram.CustomEvent<{ value: string }>) {
    this.setData({ title: e.detail.value });
  },

  onDescription(e: WechatMiniprogram.CustomEvent<{ value: string }>) {
    this.setData({ description: e.detail.value });
  },

  onWantDesc(e: WechatMiniprogram.CustomEvent<{ value: string }>) {
    this.setData({ wantDesc: e.detail.value });
  },

  onPrice(e: WechatMiniprogram.CustomEvent<{ value: string }>) {
    this.setData({ priceYuan: e.detail.value });
  },

  onBid(e: WechatMiniprogram.CustomEvent<{ value: string }>) {
    this.setData({ bidYuan: e.detail.value });
  },

  onNegotiable(e: WechatMiniprogram.CustomEvent<{ value: boolean }>) {
    this.setData({ negotiable: e.detail.value });
  },

  onPickCondition(e: WechatMiniprogram.TouchEvent) {
    this.setData({ condition: e.currentTarget.dataset.value as string });
  },

  /* ---------------- 提交 ---------------- */

  validate(): string | null {
    const d = this.data;
    const needImage = d.type !== "want";
    if (needImage && !d.images.length) return "至少上传 1 张图片";
    if (!d.title.trim()) return "起个标题吧";
    if (d.title.trim().length > 30) return "标题不超过 30 字";
    if ((d.type === "sell" || d.type === "swap") && !d.condition) return "选一下成色";
    if (d.type === "sell") {
      if (yuanToCents(d.priceYuan) === null) return "填一个正确的参考价";
    }
    if ((d.type === "swap" || d.type === "want") && !d.wantDesc.trim()) {
      return d.type === "swap" ? "说说想换什么" : "说说想要什么";
    }
    if (d.type === "want" && d.bidYuan.trim() && yuanToCents(d.bidYuan) === null) {
      return "出价格式不对，如 12.5";
    }
    return null;
  },

  async onSubmit() {
    if (this.data.submitting || this.data.uploading) return;
    const err = this.validate();
    if (err) {
      wx.showToast({ title: err, icon: "none" });
      return;
    }
    const d = this.data;
    const body: Record<string, any> = {
      type: d.type,
      title: d.title.trim(),
      description: d.description.trim(),
      // 分类免选（docs/11）：不传 category，后端按标题自动识别
      condition: d.type === "sell" || d.type === "swap" ? d.condition : null,
      price_cents: d.type === "sell" ? yuanToCents(d.priceYuan) : null,
      negotiable: d.type === "sell" ? d.negotiable : false,
      want_desc: d.type === "swap" || d.type === "want" ? d.wantDesc.trim() : null,
      bid_cents: d.type === "want" && d.bidYuan.trim() ? yuanToCents(d.bidYuan) : null,
      images: d.images,
    };
    this.setData({ submitting: true });
    try {
      const r = d.editId
        ? await put<{ id: number }>(`/api/items/${d.editId}`, body)
        : await post<{ id: number }>("/api/items", body);
      wx.showToast({ title: d.editId ? "已保存" : "发布成功", icon: "success" });
      wx.redirectTo({ url: `/pages/detail/detail?id=${r.id}` });
    } catch (e) {
      this.setData({ submitting: false });
      toastError(e);
    }
  },
});
