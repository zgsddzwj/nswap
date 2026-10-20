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

// ⚠️ 当前为「自建服务器验证」配置（2026-10-20）：
//    图片加载被微信客户端对 http 的策略拦截（wx.request/uploadFile 勾选"不校验合法域名"
//    可放行，但 <image> 组件不走该豁免）→ 过渡方案：服务器自签名 HTTPS + IP（见
//    deploy/nginx.self-signed-443.conf.example）。小程序侧需勾选
//    「不校验合法域名、web-view、TLS 版本以及 HTTPS 证书」（urlCheck:false 已预置）。
//    仅限开发调试环境；域名与备案就绪后必须改为 LOCAL_DEV 保持 false、
//    SELF_HOSTED_BASE_URL = "https://域名/nswap"
export const LOCAL_DEV = false;

/** 电脑局域网 IP（本地联调时把 LOCAL_DEV 改回 true 并同步此 IP） */
const LAN_IP = "192.168.0.230";

/**
 * 自建服务器地址（docs/13 路线 C）：填 HTTPS 域名即为自建模式。
 * 仅在 LOCAL_DEV=false 时生效；留空则走微信云托管（callContainer）。
 * 例：export const SELF_HOSTED_BASE_URL = "https://api.your-domain.com";
 * 子路径隔离部署（nginx 网关多项目同机）时带上前缀，如 "https://域名/nswap"，
 * 管理后台入口会自动推导为 https://域名/nswap/admin。
 * 当前值：自建服务器（子路径隔离 /nswap），自签名 HTTPS+IP 仅供调试。
 */
export const SELF_HOSTED_BASE_URL = "https://82.157.59.122/nswap";

/** 部署模式：local=本地联调（X-DEV-OPENID）/ cloud=微信云托管 / self=自建服务器（token） */
export type DeployMode = "local" | "cloud" | "self";
export const DEPLOY_MODE: DeployMode = LOCAL_DEV
  ? "local"
  : SELF_HOSTED_BASE_URL
    ? "self"
    : "cloud";

export const CONFIG = {
  LOCAL_DEV,
  DEPLOY_MODE,

  /**
   * 本地开发后端地址：
   * - 开发者工具模拟器可改回 http://127.0.0.1:8001
   * - 真机调试使用局域网 IP（当前已配置）
   */
  DEV_BASE_URL: `http://${LAN_IP}:8001`,

  /** 自建服务器地址（DEPLOY_MODE=self 时使用） */
  SELF_HOSTED_BASE_URL,

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

/** 当前部署模式下的后端基础地址（管理后台链接用） */
const BACKEND_BASE_URL =
  DEPLOY_MODE === "local"
    ? CONFIG.DEV_BASE_URL
    : DEPLOY_MODE === "self"
      ? SELF_HOSTED_BASE_URL
      : CONFIG.CLOUD_PUBLIC_BASE_URL;

/** 管理后台地址（「我的」页复制链接用） */
export const ADMIN_URL = `${BACKEND_BASE_URL.replace(/\/$/, "")}/admin`;

/** 协议版本（与后端 TERMS_VERSION 一致；变更后小程序会要求用户重新同意） */
export const TERMS_VERSION = "2026-10";

/** 本地开发可切换的模拟身份（与 scripts/seed.py 的演示用户一致） */
export const DEV_IDENTITIES = ["dev_alice", "dev_bob", "dev_carol"];
