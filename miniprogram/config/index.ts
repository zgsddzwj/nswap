/**
 * 运行环境配置。
 *
 * 本地开发（LOCAL_DEV = true）：
 *   - 请求直连 docker-compose 起的本地后端（默认 http://127.0.0.1:8000）
 *   - 身份通过 X-DEV-OPENID 请求头模拟，可在「我的」页切换身份
 *   - 开发者工具需勾选「不校验合法域名」（project.config.json 已置 urlCheck:false）
 *
 * 云托管生产（LOCAL_DEV = false）：
 *   - wx.cloud.init + callContainer，微信自动注入 X-WX-OPENID，免 token
 *   - CLOUD_ENV / CLOUD_SERVICE 填云托管控制台的环境 ID 与服务名
 *   - 上传走 /api/uploads/base64（callContainer 通道，鉴权随 openid 注入）
 */

export const LOCAL_DEV = true;

export const CONFIG = {
  LOCAL_DEV,

  /** 本地开发后端地址（docker-compose up 后默认 127.0.0.1:8000） */
  DEV_BASE_URL: "http://127.0.0.1:8001",

  /** 云托管环境 ID（微信云托管控制台「环境」页） */
  CLOUD_ENV: "",

  /** 云托管服务名（默认服务通常与服务名一致，部署时确认） */
  CLOUD_SERVICE: "nswap",

  /** 管理后台地址（复制到浏览器打开；本地即后端地址） */
  ADMIN_URL: "http://127.0.0.1:8001/admin",

  /**
   * 订阅消息模板 ID（微信公众平台「订阅消息」申请后填入，与后端 .env 的
   * MSG_TPL_* 对应）。留空时跳过授权请求，仅用站内通知。
   */
  SUBSCRIBE_TEMPLATES: {
    want: "", // 新意向 → 卖家
    accepted: "", // 意向被接受 → 买家
    confirm: "", // 待确认提醒 → 双方
    review: "", // 新评价 → 对方
  } as Record<"want" | "accepted" | "confirm" | "review", string>,
};

/** 本地开发可切换的模拟身份（与 scripts/seed.py 的演示用户一致） */
export const DEV_IDENTITIES = ["dev_alice", "dev_bob", "dev_carol"];
