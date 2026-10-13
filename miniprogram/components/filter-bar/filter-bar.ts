import { ITEM_TYPES, CATEGORIES, EnumMeta } from "../../utils/constants";

Component({
  properties: {
    type: { type: String, value: "" },
    category: { type: String, value: "" },
    building: { type: String, value: "" },
    buildings: { type: Array, value: [] as string[] },
  },

  data: {
    typeChips: [] as EnumMeta[],
    categoryChips: [] as EnumMeta[],
  },

  lifetimes: {
    attached(this: any) {
      this.setData({
        typeChips: ITEM_TYPES,
        categoryChips: CATEGORIES,
      });
    },
  },

  methods: {
    onTypeTap(this: any, e: WechatMiniprogram.TouchEvent) {
      const type = e.currentTarget.dataset.value as string;
      this.triggerEvent("change", { type, category: this.data.category, building: this.data.building });
    },
    onCategoryTap(this: any, e: WechatMiniprogram.TouchEvent) {
      const category = e.currentTarget.dataset.value as string;
      this.triggerEvent("change", { type: this.data.type, category, building: this.data.building });
    },
    onBuildingChange(this: any, e: WechatMiniprogram.PickerChange) {
      const idx = Number(e.detail.value);
      const building = this.data.buildings[idx] || "";
      this.triggerEvent("change", { type: this.data.type, category: this.data.category, building });
    },
  },
});
