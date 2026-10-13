/** 格式化工具：金额（分↔元）、时间、好评率 */

/** 分 → 元字符串。15000 → "150"，15050 → "150.5"（配合 ns-price 分段渲染） */
export function splitPrice(cents: number | null | undefined): { int: string; dec: string } {
  if (cents === null || cents === undefined || isNaN(cents)) return { int: "0", dec: "" };
  const yuan = cents / 100;
  const s = yuan % 1 === 0 ? String(yuan) : String(Number(yuan.toFixed(2)));
  const dot = s.indexOf(".");
  if (dot === -1) return { int: s, dec: "" };
  return { int: s.slice(0, dot), dec: s.slice(dot) };
}

/** 元字符串 → 分。输入非法返回 null（表单校验用） */
export function yuanToCents(input: string): number | null {
  const s = (input || "").trim();
  if (!s) return null;
  if (!/^\d+(\.\d{1,2})?$/.test(s)) return null;
  const cents = Math.round(parseFloat(s) * 100);
  if (cents <= 0) return null;
  return cents;
}

/** 相对时间：刚刚 / n分钟前 / n小时前 / 昨天 / n天前 / MM-DD / YYYY-MM-DD */
export function relTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const diff = Date.now() - d.getTime();
  const min = Math.floor(diff / 60000);
  if (min < 1) return "刚刚";
  if (min < 60) return `${min}分钟前`;
  const hour = Math.floor(min / 60);
  if (hour < 24) return `${hour}小时前`;
  const day = Math.floor(hour / 24);
  if (day === 1) return "昨天";
  if (day < 8) return `${day}天前`;
  const now = new Date();
  const pad = (n: number) => (n < 10 ? `0${n}` : String(n));
  const md = `${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  if (d.getFullYear() === now.getFullYear()) return md;
  return `${d.getFullYear()}-${md}`;
}

/** 绝对时间：MM-DD HH:mm（约定时间等场景） */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const pad = (n: number) => (n < 10 ? `0${n}` : String(n));
  return `${d.getMonth() + 1}月${d.getDate()}日 ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** 好评率：好评 / 总评价，无评价显示 "--" */
export function goodRate(stats: {
  review_good: number;
  review_mid: number;
  review_bad: number;
}): string {
  const total = stats.review_good + stats.review_mid + stats.review_bad;
  if (total === 0) return "--";
  return `${Math.round((stats.review_good / total) * 100)}%`;
}

/** 累计成交数（卖+送+换） */
export function tradesDone(stats: {
  sell_done: number;
  give_done: number;
  swap_done: number;
}): number {
  return stats.sell_done + stats.give_done + stats.swap_done;
}

/** Date → 后端约定的 ISO8601 UTC 字符串（约定时间提交用） */
export function toIso(d: Date): string {
  const pad = (n: number) => (n < 10 ? `0${n}` : String(n));
  return (
    `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}` +
    `T${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:00Z`
  );
}
