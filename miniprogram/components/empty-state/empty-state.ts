Component({
  properties: {
    icon: { type: String, value: "info-circle" },
    text: { type: String, value: "这里还什么都没有" },
    sub: { type: String, value: "" },
    actionText: { type: String, value: "" },
  },

  methods: {
    onAction(this: any) {
      this.triggerEvent("action");
    },
  },
});
