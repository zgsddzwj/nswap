/**
 * 小程序结构校验（CI 与本地通用，docs/09 P1-9）
 * 校验：JSON 可解析；app.json 页面 ↔ 磁盘四件套；usingComponents 路径存在；
 *       tabBar 图标存在；wxml 中使用的 t-* 组件已全局注册。
 * 用法：node scripts/validate.mjs
 */
import { readFileSync, existsSync } from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const errors = [];

function readJson(rel, label) {
  try {
    return JSON.parse(readFileSync(path.join(root, rel), "utf8"));
  } catch (e) {
    errors.push(`${label || rel}: JSON 解析失败 ${e.message}`);
    return null;
  }
}

const app = readJson("app.json");
if (!app) {
  console.error(errors.join("\n"));
  process.exit(1);
}

for (const f of ["theme.json", "sitemap.json", "project.config.json", "package.json", "tsconfig.json"]) {
  readJson(f);
}

// 页面四件套
for (const page of app.pages) {
  for (const ext of ["ts", "json", "wxml", "wxss"]) {
    if (!existsSync(path.join(root, `${page}.${ext}`))) errors.push(`页面缺文件: ${page}.${ext}`);
  }
  const pj = readJson(`${page}.json`, page);
  if (pj) {
    for (const [name, comp] of Object.entries(pj.usingComponents || {})) {
      const base = comp.startsWith("/")
        ? comp.slice(1)
        : path.posix.join(path.posix.dirname(page), comp);
      if (!existsSync(path.join(root, `${base}.json`))) {
        errors.push(`${page} 引用组件缺失: ${name} -> ${comp}`);
      }
    }
  }
}

// 全局组件（自研四件套；tdesign 由 npm 构建产出）
for (const [name, comp] of Object.entries(app.usingComponents || {})) {
  if (comp.startsWith("/components/")) {
    const base = comp.slice(1);
    for (const ext of ["ts", "json", "wxml", "wxss"]) {
      if (!existsSync(path.join(root, `${base}.${ext}`))) errors.push(`自研组件缺文件: ${base}.${ext}`);
    }
  }
}

// tabBar 图标与页面注册
for (const item of app.tabBar?.list || []) {
  for (const k of ["iconPath", "selectedIconPath"]) {
    if (!existsSync(path.join(root, item[k]))) errors.push(`tabBar 图标缺失: ${item[k]}`);
  }
  if (!app.pages.includes(item.pagePath)) errors.push(`tabBar 页未注册: ${item.pagePath}`);
}

// wxml 中的 t-* 组件必须已注册
const registered = new Set(Object.keys(app.usingComponents || {}));
for (const page of app.pages) {
  const wxml = readFileSync(path.join(root, `${page}.wxml`), "utf8");
  for (const m of new Set([...wxml.matchAll(/<(t-[a-z-]+)[\s>]/g)].map((x) => x[1]))) {
    if (!registered.has(m)) errors.push(`${page} 使用未注册组件 <${m}>`);
  }
}

if (errors.length) {
  console.error("结构校验失败：");
  for (const e of errors) console.error("  ✗ " + e);
  process.exit(1);
}
console.log(`结构校验通过（${app.pages.length} 页）`);
