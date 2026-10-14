import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { api, type Page } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Badge, Card, CardHeader, Empty, PageHeader } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { fmtTime } from "@/lib/utils";

interface UserRow {
  id: number;
  nickname: string;
  building: string;
  unit: string;
  community_id: number | null;
  community_name: string;
  role: string;
  verified: boolean;
  status: string;
  trades_done: number;
  violations: number;
  created_at: string;
}

interface VerifyRow {
  id: number;
  user: { id: number; nickname: string | null };
  building: string;
  unit: string;
  proof_image: string;
  community_name: string;
  created_at: string;
}

function RoleBadge({ role }: { role: string }) {
  if (role === "admin") return <Badge tone="blue">管理员</Badge>;
  if (role === "elder") return <Badge tone="amber">楼长</Badge>;
  return <Badge tone="gray">住户</Badge>;
}

export function Users() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [action, setAction] = useState<{ user: UserRow; kind: "ban" | "unban" | "elder" } | null>(null);
  const [rejecting, setRejecting] = useState<VerifyRow | null>(null);
  const [rejectNote, setRejectNote] = useState("");

  const { data } = useQuery({
    queryKey: ["admin-users", page, q],
    queryFn: () =>
      api<Page<UserRow>>(
        "GET",
        `/api/admin/users?page=${page}&page_size=20${q ? `&q=${encodeURIComponent(q)}` : ""}`
      ),
  });
  const { data: verify } = useQuery({
    queryKey: ["verify-requests", page],
    queryFn: () => api<Page<VerifyRow>>("GET", `/api/admin/verify-requests?page=${page}&page_size=20`),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin-users"] });
    qc.invalidateQueries({ queryKey: ["verify-requests"] });
    qc.invalidateQueries({ queryKey: ["stats"] });
  };

  const userAction = useMutation({
    mutationFn: (v: { id: number; kind: string }) => api("POST", `/api/admin/users/${v.id}/${v.kind}`),
    onSuccess: (_d, v) => {
      toast.success(v.kind === "ban" ? "已封禁" : v.kind === "unban" ? "已解封" : "角色已更新");
      setAction(null);
      invalidate();
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "操作失败"),
  });

  const approve = useMutation({
    mutationFn: (id: number) => api("POST", `/api/admin/verify-requests/${id}/approve`),
    onSuccess: () => {
      toast.success("已通过验证");
      invalidate();
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "操作失败"),
  });
  const reject = useMutation({
    mutationFn: (v: { id: number; note: string }) =>
      api("POST", `/api/admin/verify-requests/${v.id}/reject`, { note: v.note }),
    onSuccess: () => {
      toast.success("已驳回");
      setRejecting(null);
      setRejectNote("");
      invalidate();
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "操作失败"),
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / 20)) : 1;
  const ACTION_LABEL = { ban: "封禁", unban: "解封", elder: "切换楼长角色" };

  return (
    <div>
      <PageHeader title="用户管理" />

      {verify && verify.list.length > 0 && (
        <Card className="mb-5">
          <CardHeader title="待审核的人工验证申请" />
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs text-slate-400">
                <th className="px-5 py-2.5 font-medium">#</th>
                <th className="px-5 py-2.5 font-medium">申请人</th>
                <th className="px-5 py-2.5 font-medium">楼栋</th>
                <th className="px-5 py-2.5 font-medium">小区</th>
                <th className="px-5 py-2.5 font-medium">凭证</th>
                <th className="px-5 py-2.5 font-medium">申请时间</th>
                <th className="px-5 py-2.5"></th>
              </tr>
            </thead>
            <tbody>
              {verify.list.map((vr) => (
                <tr key={vr.id} className="border-b border-slate-50 last:border-0">
                  <td className="px-5 py-2.5 text-slate-400">{vr.id}</td>
                  <td className="px-5 py-2.5 text-slate-700">
                    #{vr.user.id} {vr.user.nickname ?? ""}
                  </td>
                  <td className="px-5 py-2.5">
                    {vr.building} {vr.unit}
                  </td>
                  <td className="px-5 py-2.5 text-slate-500">{vr.community_name}</td>
                  <td className="px-5 py-2.5">
                    <a
                      href={vr.proof_image}
                      target="_blank"
                      rel="noreferrer"
                      className="text-brand hover:underline"
                    >
                      查看凭证
                    </a>
                  </td>
                  <td className="px-5 py-2.5 text-slate-500">{fmtTime(vr.created_at)}</td>
                  <td className="px-5 py-2.5">
                    <div className="flex gap-2">
                      <Button className="px-2.5 py-1 text-xs" onClick={() => approve.mutate(vr.id)}>
                        通过
                      </Button>
                      <Button
                        variant="outline"
                        className="px-2.5 py-1 text-xs"
                        onClick={() => setRejecting(vr)}
                      >
                        驳回
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <Card className="mb-5 p-4">
        <form
          className="flex gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            setPage(1);
            qc.invalidateQueries({ queryKey: ["admin-users"] });
          }}
        >
          <Input
            className="w-64"
            placeholder="按昵称搜索"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <Button variant="secondary">搜索</Button>
        </form>
      </Card>

      <Card>
        {!data || data.list.length === 0 ? (
          <Empty />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs text-slate-400">
                <th className="px-5 py-2.5 font-medium">#</th>
                <th className="px-5 py-2.5 font-medium">小区</th>
                <th className="px-5 py-2.5 font-medium">昵称</th>
                <th className="px-5 py-2.5 font-medium">楼栋</th>
                <th className="px-5 py-2.5 font-medium">角色</th>
                <th className="px-5 py-2.5 font-medium">验证</th>
                <th className="px-5 py-2.5 font-medium">状态</th>
                <th className="px-5 py-2.5 font-medium">交易</th>
                <th className="px-5 py-2.5 font-medium">违约</th>
                <th className="px-5 py-2.5 font-medium">注册时间</th>
                <th className="px-5 py-2.5"></th>
              </tr>
            </thead>
            <tbody>
              {data.list.map((u) => (
                <tr key={u.id} className="border-b border-slate-50 last:border-0">
                  <td className="px-5 py-2.5 text-slate-400">{u.id}</td>
                  <td className="px-5 py-2.5 text-slate-500">{u.community_name}</td>
                  <td className="px-5 py-2.5 font-medium text-slate-700">{u.nickname}</td>
                  <td className="px-5 py-2.5">
                    {u.building}
                    {u.unit ? ` ${u.unit}` : ""}
                  </td>
                  <td className="px-5 py-2.5">
                    <RoleBadge role={u.role} />
                  </td>
                  <td className="px-5 py-2.5">
                    {u.verified ? <Badge tone="green">已验证</Badge> : <Badge tone="gray">未验证</Badge>}
                  </td>
                  <td className="px-5 py-2.5">
                    {u.status === "active" ? (
                      <Badge tone="green">正常</Badge>
                    ) : (
                      <Badge tone="red">已封禁</Badge>
                    )}
                  </td>
                  <td className="px-5 py-2.5">{u.trades_done}</td>
                  <td className="px-5 py-2.5">{u.violations > 0 ? <Badge tone="red">{u.violations}</Badge> : 0}</td>
                  <td className="px-5 py-2.5 text-slate-500">{fmtTime(u.created_at)}</td>
                  <td className="px-5 py-2.5">
                    <div className="flex gap-1.5">
                      {u.status === "active" ? (
                        <Button
                          variant="outline"
                          className="px-2 py-1 text-xs"
                          onClick={() => setAction({ user: u, kind: "ban" })}
                        >
                          封禁
                        </Button>
                      ) : (
                        <Button
                          variant="outline"
                          className="px-2 py-1 text-xs"
                          onClick={() => setAction({ user: u, kind: "unban" })}
                        >
                          解封
                        </Button>
                      )}
                      <Button
                        variant="secondary"
                        className="px-2 py-1 text-xs"
                        onClick={() => setAction({ user: u, kind: "elder" })}
                      >
                        {u.role === "elder" ? "撤楼长" : "设楼长"}
                      </Button>
                    </div>
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

      <Modal open={!!action} onClose={() => setAction(null)} title="确认操作">
        <p className="mb-4 text-sm text-slate-600">
          确认对「{action?.user.nickname}」{action ? ACTION_LABEL[action.kind] : ""}？
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setAction(null)}>
            取消
          </Button>
          <Button
            variant={action?.kind === "ban" ? "danger" : "primary"}
            onClick={() => action && userAction.mutate({ id: action.user.id, kind: action.kind })}
          >
            确认
          </Button>
        </div>
      </Modal>

      <Modal open={!!rejecting} onClose={() => setRejecting(null)} title="驳回验证申请">
        <textarea
          className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand focus:outline-none"
          rows={2}
          placeholder="驳回原因（选填）"
          value={rejectNote}
          onChange={(e) => setRejectNote(e.target.value)}
        />
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setRejecting(null)}>
            取消
          </Button>
          <Button
            variant="danger"
            onClick={() => rejecting && reject.mutate({ id: rejecting.id, note: rejectNote })}
          >
            确认驳回
          </Button>
        </div>
      </Modal>
    </div>
  );
}
