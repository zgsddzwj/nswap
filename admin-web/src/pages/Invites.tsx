import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Copy, KeyRound } from "lucide-react";
import { toast } from "sonner";
import { api, type AdminInfo, type Page } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Input";
import { Badge, Card, Empty, PageHeader } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { fmtTime } from "@/lib/utils";

interface InviteRow {
  id: number;
  code: string;
  kind: string;
  building: string;
  batch_note: string;
  status: string;
  used_by: number | null;
  expires_at: string | null;
  community_id: number;
  community_name: string;
  created_at: string;
}

interface CommunityRow {
  id: number;
  name: string;
  city: string;
  status: string;
}

function StatusBadge({ status }: { status: string }) {
  if (status === "active") return <Badge tone="green">可用</Badge>;
  if (status === "used") return <Badge tone="gray">已使用</Badge>;
  return <Badge tone="amber">已作废</Badge>;
}

export function Invites() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [created, setCreated] = useState<string[] | null>(null);
  const { data: admin } = useQuery({
    queryKey: ["me"],
    queryFn: () => api<AdminInfo>("GET", "/api/admin/auth/me"),
    staleTime: 60_000,
  });
  const isSuper = admin?.role === "super";

  const { data } = useQuery({
    queryKey: ["invites", page, status],
    queryFn: () =>
      api<Page<InviteRow>>(
        "GET",
        `/api/admin/invites?page=${page}&page_size=20${status ? `&status=${status}` : ""}`
      ),
  });

  const communities = useQuery({
    queryKey: ["communities-lite"],
    queryFn: () => api<{ list: CommunityRow[] }>("GET", "/api/admin/communities"),
    enabled: !!isSuper,
  });

  const [form, setForm] = useState({ building: "", count: 10, days: 14, batch_note: "", community_id: 0 });
  const generate = useMutation({
    mutationFn: () =>
      api<{ created: string[] }>("POST", "/api/admin/invites", {
        ...form,
        community_id: isSuper ? form.community_id || null : null,
      }),
    onSuccess: (d) => {
      setCreated(d.created);
      toast.success(`已生成 ${d.created.length} 个邀请码`);
      qc.invalidateQueries({ queryKey: ["invites"] });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "生成失败"),
  });

  const revoke = useMutation({
    mutationFn: (id: number) => api("POST", `/api/admin/invites/${id}/revoke`),
    onSuccess: () => {
      toast.success("已作废");
      qc.invalidateQueries({ queryKey: ["invites"] });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "操作失败"),
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / 20)) : 1;

  return (
    <div>
      <PageHeader title="邀请码管理">
        <span className="text-sm text-slate-400">
          {isSuper ? "全部小区" : `小区：${admin?.community?.name ?? "-"}`}
        </span>
      </PageHeader>

      <Card className="mb-5 p-5">
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            generate.mutate();
          }}
        >
          {isSuper && (
            <Field label="目标小区">
              <Select
                className="w-44"
                required
                value={form.community_id || ""}
                onChange={(e) => setForm({ ...form, community_id: Number(e.target.value) })}
              >
                <option value="" disabled>
                  选择小区
                </option>
                {(communities.data?.list ?? [])
                  .filter((c) => c.status === "active")
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}（{c.city}）
                    </option>
                  ))}
              </Select>
            </Field>
          )}
          <Field label="楼栋">
            <Input
              className="w-28"
              required
              placeholder="如 3栋"
              value={form.building}
              onChange={(e) => setForm({ ...form, building: e.target.value })}
            />
          </Field>
          <Field label="数量">
            <Input
              className="w-20"
              type="number"
              min={1}
              max={100}
              value={form.count}
              onChange={(e) => setForm({ ...form, count: Number(e.target.value) })}
            />
          </Field>
          <Field label="有效期(天)">
            <Input
              className="w-20"
              type="number"
              min={1}
              max={90}
              value={form.days}
              onChange={(e) => setForm({ ...form, days: Number(e.target.value) })}
            />
          </Field>
          <Field label="批次备注">
            <Input
              className="w-40"
              placeholder="如 居委会首发"
              value={form.batch_note}
              onChange={(e) => setForm({ ...form, batch_note: e.target.value })}
            />
          </Field>
          <Button disabled={generate.isPending}>
            <KeyRound size={14} /> 批量生成
          </Button>
        </form>
      </Card>

      <Card>
        <div className="flex items-center gap-2 border-b border-slate-100 px-5 py-3">
          {["", "active", "used", "revoked"].map((s) => (
            <button
              key={s}
              onClick={() => {
                setStatus(s);
                setPage(1);
              }}
              className={`rounded-full px-3 py-1 text-xs font-medium ${
                status === s ? "bg-brand text-white" : "text-slate-500 hover:bg-slate-100"
              }`}
            >
              {s === "" ? "全部" : s === "active" ? "可用" : s === "used" ? "已使用" : "已作废"}
            </button>
          ))}
        </div>
        {!data || data.list.length === 0 ? (
          <Empty />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs text-slate-400">
                <th className="px-5 py-2.5 font-medium">码</th>
                <th className="px-5 py-2.5 font-medium">类型</th>
                {isSuper && <th className="px-5 py-2.5 font-medium">小区</th>}
                <th className="px-5 py-2.5 font-medium">楼栋</th>
                <th className="px-5 py-2.5 font-medium">批次</th>
                <th className="px-5 py-2.5 font-medium">状态</th>
                <th className="px-5 py-2.5 font-medium">过期时间</th>
                <th className="px-5 py-2.5"></th>
              </tr>
            </thead>
            <tbody>
              {data.list.map((inv) => (
                <tr key={inv.id} className="border-b border-slate-50 last:border-0">
                  <td className="px-5 py-2.5">
                    <code className="rounded bg-slate-50 px-1.5 py-0.5 text-xs text-brand">{inv.code}</code>
                  </td>
                  <td className="px-5 py-2.5">{inv.kind === "vouch" ? "担保码" : "普通"}</td>
                  {isSuper && <td className="px-5 py-2.5 text-slate-500">{inv.community_name}</td>}
                  <td className="px-5 py-2.5">{inv.building}</td>
                  <td className="px-5 py-2.5 text-slate-500">{inv.batch_note || "-"}</td>
                  <td className="px-5 py-2.5">
                    <StatusBadge status={inv.status} />
                  </td>
                  <td className="px-5 py-2.5 text-slate-500">{fmtTime(inv.expires_at)}</td>
                  <td className="px-5 py-2.5">
                    {inv.status === "active" && (
                      <Button
                        variant="outline"
                        className="px-2.5 py-1 text-xs"
                        onClick={() => {
                          if (confirm("确认作废该邀请码？")) revoke.mutate(inv.id);
                        }}
                      >
                        作废
                      </Button>
                    )}
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

      <Modal open={!!created} onClose={() => setCreated(null)} title="邀请码已生成">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-sm text-slate-500">请复制后通过组织渠道发放给住户</span>
          <Button
            variant="secondary"
            className="px-2.5 py-1 text-xs"
            onClick={() => {
              navigator.clipboard.writeText((created ?? []).join("\n"));
              toast.success("已复制全部邀请码");
            }}
          >
            <Copy size={13} /> 复制全部
          </Button>
        </div>
        <div className="max-h-64 overflow-auto rounded-lg border border-slate-200">
          {(created ?? []).map((c) => (
            <div key={c} className="border-b border-slate-50 px-4 py-2 last:border-0">
              <code className="text-sm font-semibold text-brand">{c}</code>
            </div>
          ))}
        </div>
      </Modal>
    </div>
  );
}
