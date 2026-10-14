import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, type Page } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card, Empty, PageHeader } from "@/components/ui/Card";
import { fmtTime } from "@/lib/utils";

interface LogRow {
  id: number;
  admin_id: number;
  admin_name: string;
  action: string;
  target_type: string | null;
  target_id: number | null;
  detail: string | null;
  created_at: string;
}

const ACTION_LABEL: Record<string, string> = {
  create_invites: "生成邀请码",
  revoke_invite: "作废邀请码",
  create_announcement: "发布公告",
  update_announcement: "编辑公告",
  delete_announcement: "删除公告",
  force_off_shelf: "强制下架",
  report_resolve: "举报处置",
  report_dismiss: "举报驳回",
  ban_user: "封禁用户",
  unban_user: "解封用户",
  toggle_elder: "切换楼长",
  approve_verify: "通过验证",
  reject_verify: "驳回验证",
  create_community: "开通小区",
  toggle_community: "启停小区",
  reset_community_password: "重置物业密码",
  change_password: "修改密码",
  login_failed: "登录失败",
  approve_item: "放行物品",
  reject_item: "拒绝物品",
  approve_message: "放行留言",
  reject_message: "拒绝留言",
  user_self_delete: "用户注销",
};

export function Logs() {
  const [page, setPage] = useState(1);
  const [action, setAction] = useState("");
  const { data } = useQuery({
    queryKey: ["logs", page, action],
    queryFn: () =>
      api<Page<LogRow>>(
        "GET",
        `/api/admin/logs?page=${page}&page_size=20${action ? `&action=${action}` : ""}`
      ),
  });
  const totalPages = data ? Math.max(1, Math.ceil(data.total / 20)) : 1;

  return (
    <div>
      <PageHeader title="操作日志" />
      <Card className="mb-4 p-4">
        <select
          className="w-48 rounded-lg border border-slate-300 px-3 py-2 text-sm"
          value={action}
          onChange={(e) => {
            setAction(e.target.value);
            setPage(1);
          }}
        >
          <option value="">全部动作</option>
          {Object.entries(ACTION_LABEL).map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      </Card>
      <Card>
        {!data || data.list.length === 0 ? (
          <Empty text="暂无操作日志" />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs text-slate-400">
                <th className="px-5 py-2.5 font-medium">时间</th>
                <th className="px-5 py-2.5 font-medium">操作者</th>
                <th className="px-5 py-2.5 font-medium">动作</th>
                <th className="px-5 py-2.5 font-medium">对象</th>
                <th className="px-5 py-2.5 font-medium">详情</th>
              </tr>
            </thead>
            <tbody>
              {data.list.map((r) => (
                <tr key={r.id} className="border-b border-slate-50 last:border-0">
                  <td className="px-5 py-2.5 text-slate-500">{fmtTime(r.created_at)}</td>
                  <td className="px-5 py-2.5 text-slate-700">{r.admin_name}</td>
                  <td className="px-5 py-2.5">{ACTION_LABEL[r.action] ?? r.action}</td>
                  <td className="px-5 py-2.5 text-slate-500">
                    {r.target_type ? `${r.target_type}#${r.target_id ?? "-"}` : "-"}
                  </td>
                  <td className="max-w-md px-5 py-2.5 text-slate-500">
                    <span className="line-clamp-1">{r.detail || "-"}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {data && data.total > 20 && (
          <div className="flex items-center justify-between border-t border-slate-100 px-5 py-3 text-sm text-slate-500">
            <span>
              共 {data.total} 条 · 第 {page}/{totalPages} 页
            </span>
            <div className="flex gap-2">
              <Button variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                上一页
              </Button>
              <Button variant="outline" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
                下一页
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
