/**
 * 运行环境配置。
 *
 * 本地开发（LOCAL_DEV = true）：
 *   - 请求直连本机后端（模拟器用 127.0.0.1，真机用局域网 IP）
 *   - 身份通过 X-DEV-OPENID 请求头模拟，可在「我的」页切换身份
 *
 * 【真机调试必读】
 *   1. 手机与电脑连同一个 Wi-Fi；
 *   2. LAN_IP 填电脑的局域网 IP（终端执行 `ipconfig getifaddr en0` 查看），
 *      IP 变了要同步改这里；
 *   3. 后端需监听 0.0.0.0（uvicorn 加 --host 0.0.0.0）；
 *   4. 真机上打开小程序后：右上角胶囊 → 开发调试 → 打开调试（绕过域名校验，
 *      否则 HTTP + IP 请求会被微信拦截）；macOS 首次需允许防火墙入站；
 *   5. 游客模式（touristappid）不支持真机预览，真机调试需在
 *      project.config.json 填自己的 AppID。
 *
 * 云托管生产（LOCAL_DEV = false）：
 *   - wx.cloud.init + callContainer，微信自动注入 X-WX-OPENID（真实登录），免 token
 *   - CLOUD_ENV / CLOUD_SERVICE 填云托管控制台的环境 ID 与服务名
 *   - 上传走 /api/uploads/base64（callContainer 通道，鉴权随 openid 注入）
 */

export const LOCAL_DEV = true;

/** 电脑局域网 IP（`ipconfig getifaddr en0`），换网络后同步更新 */
const LAN_IP = "192.168.0.230";

export const CONFIG = {
  LOCAL_DEV,

  /**
   * 本地开发后端地址：
   * - 开发者工具模拟器可改回 http://127.0.0.1:8001
   * - 真机调试使用局域网 IP（当前已配置）
   */
  DEV_BASE_URL: `http://${LAN_IP}:8001`,

  /** 云托管环境 ID（微信云托管控制台「环境」页） */
  CLOUD_ENV: "",

  /** 云托管服务名（部署时确认，默认与服务名一致） */
  CLOUD_SERVICE: "nswap",

  /** 云托管容器的公网域名（控制台「服务设置-公网访问」），用于管理后台链接 */
  CLOUD_PUBLIC_BASE_URL: "",

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

/** 管理后台地址（「我的」页复制链接用） */
export const ADMIN_URL = LOCAL_DEV
  ? `${CONFIG.DEV_BASE_URL}/admin`
  : `${CONFIG.CLOUD_PUBLIC_BASE_URL.replace(/\/$/, "")}/admin`;

/** 协议版本（与后端 TERMS_VERSION 一致；变更后小程序会要求用户重新同意） */
export const TERMS_VERSION = "2026-10";

/** 本地开发可切换的模拟身份（与 scripts/seed.py 的演示用户一致） */
export const DEV_IDENTITIES = ["dev_alice", "dev_bob", "dev_carol"];
