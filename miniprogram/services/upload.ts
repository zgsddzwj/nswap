/**
 * 图片上传：压缩 → 上传 → 返回可入库的完整 URL。
 * - 本地开发：wx.uploadFile multipart 直连本地后端（X-DEV-OPENID 鉴权）
 * - 云托管：callContainer 的 JSON base64 通道（openid 由微信注入；
 *   wx.uploadFile 直连公网域名无法注入身份，故走 /api/uploads/base64）
 */
import { CONFIG, LOCAL_DEV } from "../config/index";
import { devOpenid, post } from "./api";

const ALLOWED_EXT = [".jpg", ".jpeg", ".png", ".webp"];

function extOf(path: string): string {
  const m = /\.([a-zA-Z0-9]+)$/.exec(path || "");
  return m ? `.${m[1].toLowerCase()}` : ".jpg";
}

/** 压缩（质量 70）；开发者工具部分环境不支持时回退原图 */
async function compress(src: string): Promise<string> {
  try {
    const res = await wx.compressImage({ src, quality: 70 });
    if (res && res.tempFilePath) return res.tempFilePath;
  } catch {
    /* ignore */
  }
  return src;
}

function multipartUpload(filePath: string): Promise<string> {
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: CONFIG.DEV_BASE_URL + "/api/uploads",
      filePath,
      name: "file",
      header: { "X-DEV-OPENID": devOpenid() },
      success: (res) => {
        try {
          const body = JSON.parse(res.data);
          if (res.statusCode >= 200 && res.statusCode < 300 && body.code === 0) {
            resolve(body.data.url as string);
          } else {
            reject(new Error(body.message || "图片上传失败"));
          }
        } catch {
          reject(new Error("图片上传失败"));
        }
      },
      fail: () => reject(new Error("图片上传失败，请检查网络")),
    });
  });
}

/** 上传单张图片（先压缩） */
export async function uploadImage(tempFilePath: string): Promise<string> {
  const src = await compress(tempFilePath);
  if (ALLOWED_EXT.indexOf(extOf(src)) === -1) {
    throw new Error("仅支持 jpg/png/webp 图片");
  }
  if (LOCAL_DEV) {
    return multipartUpload(src);
  }
  const fs = wx.getFileSystemManager();
  const content = fs.readFileSync(src, "base64");
  const r = await post<{ url: string }>("/api/uploads/base64", {
    filename: `upload${extOf(src)}`,
    content,
  });
  return r.url;
}

/** 选图（相册/相机） */
export async function chooseImages(remaining: number): Promise<string[]> {
  if (remaining <= 0) {
    wx.showToast({ title: "最多 9 张图片", icon: "none" });
    return [];
  }
  const res = await wx.chooseMedia({
    count: remaining,
    mediaType: ["image"],
    sourceType: ["album", "camera"],
    sizeType: ["compressed"],
  });
  return res.tempFiles.map((f) => f.tempFilePath);
}

/** 批量上传（逐张压缩上传，onProgress 汇报进度） */
export async function uploadImages(
  paths: string[],
  onProgress?: (done: number, total: number) => void
): Promise<string[]> {
  const urls: string[] = [];
  for (let i = 0; i < paths.length; i++) {
    const url = await uploadImage(paths[i]);
    urls.push(url);
    onProgress && onProgress(i + 1, paths.length);
  }
  return urls;
}
