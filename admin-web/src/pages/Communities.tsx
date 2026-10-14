import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Copy } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Input";
import { Badge, Card, PageHeader } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { fmtTime } from "@/lib/utils";

interface CommunityRow {
  id: number;
  name: string;
  city: string;
  district: string;
  address: string;
  status: string;
  users: number;
  items: number;
  admins: { username: string; name: string }[];
  created_at: string;
}

export function Communities() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [resetFor, setResetFor] = useState<CommunityRow | null>(null);
  const [newPassword, setNewPassword] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    city: "",
    district: "",
    address: "",
    admin_username: "",
    admin_name: "",
    admin_password: "",
  });

  const { data } = useQuery({
    queryKey: ["communities"],
    queryFn: () => api<{ list: CommunityRow[] }>("GET", "/api/admin/communities"),
  });

  const create = useMutation({
    mutationFn: () => api<{ id: number }>("POST", "/api/admin/communities", form),
    onSuccess: () => {
      toast.success(`小区「${form.name}」已开通`);
      setCreateOpen(false);
      setForm({
        name: "",
        city: "",
        district: "",
        address: "",
        admin_username: "",
        admin_name: "",
        admin_password: "",
      });
      qc.invalidateQueries({ queryKey: ["communities"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "开通失败"),
  });

  const toggle = useMutation({
    mutationFn: (id: number) => api<{ status: string }>(`POST`, `/api/admin/communities/${id}/toggle-status`),
    onSuccess: () => {
      toast.success("状态已更新");
      qc.invalidateQueries({ queryKey: ["communities"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "操作失败"),
  });

  const resetPassword = useMutation({
    mutationFn: (id: number) => api<{ new_password: string }>(`POST`, `/api/admin/communities/${id}/reset-password`),
    onSuccess: (d) => {
      setNewPassword(d.new_password);
      setResetFor(null);
      toast.success("密码已重置");
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "操作失败"),
  });

  return (
    <div>
      <PageHeader title="小区管理">
        <Button onClick={() => setCreateOpen(true)}>开通新小区</Button>
      </PageHeader>

      <Card>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-left text-xs text-slate-400">
              <th className="px-5 py-2.5 font-medium">#</th>
              <th className="px-5 py-2.5 font-medium">名称</th>
              <th className="px-5 py-2.5 font-medium">城市</th>
              <th className="px-5 py-2.5 font-medium">状态</th>
              <th className="px-5 py-2.5 font-medium">住户</th>
              <th className="px-5 py-2.5 font-medium">物品</th>
              <th className="px-5 py-2.5 font-medium">物业账号</th>
              <th className="px-5 py-2.5 font-medium">开通时间</th>
              <th className="px-5 py-2.5"></th>
            </tr>
          </thead>
          <tbody>
            {(data?.list ?? []).map((c) => (
              <tr key={c.id} className="border-b border-slate-50 last:border-0">
                <td className="px-5 py-2.5 text-slate-400">{c.id}</td>
                <td className="px-5 py-2.5 font-medium text-slate-700">{c.name}</td>
                <td className="px-5 py-2.5 text-slate-500">
                  {c.city}
                  {c.district ? ` · ${c.district}` : ""}
                </td>
                <td className="px-5 py-2.5">
                  {c.status === "active" ? (
                    <Badge tone="green">正常</Badge>
                  ) : (
                    <Badge tone="gray">已停用</Badge>
                  )}
                </td>
                <td className="px-5 py-2.5">{c.users}</td>
                <td className="px-5 py-2.5">{c.items}</td>
                <td className="px-5 py-2.5 text-slate-500">
                  {c.admins.map((a) => a.username).join("、") || "-"}
                </td>
                <td className="px-5 py-2.5 text-slate-500">{fmtTime(c.created_at)}</td>
                <td className="px-5 py-2.5">
                  <div className="flex gap-1.5">
                    <Button
                      variant={c.status === "active" ? "outline" : "primary"}
                      className="px-2 py-1 text-xs"
                      onClick={() => {
                        if (confirm(`确认${c.status === "active" ? "停用" : "启用"}「${c.name}」？`)) {
                          toggle.mutate(c.id);
                        }
                      }}
                    >
                      {c.status === "active" ? "停用" : "启用"}
                    </Button>
                    <Button
                      variant="secondary"
                      className="px-2 py-1 text-xs"
                      onClick={() => setResetFor(c)}
                    >
                      重置物业密码
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="开通新小区" wide>
        <form
          className="grid grid-cols-2 gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <Field label="小区名称">
            <Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </Field>
          <Field label="城市（必填，同城维度）">
            <Input required value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} />
          </Field>
          <Field label="区">
            <Input value={form.district} onChange={(e) => setForm({ ...form, district: e.target.value })} />
          </Field>
          <Field label="地址">
            <Input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
          </Field>
          <Field label="物业账号用户名">
            <Input
              required
              minLength={3}
              value={form.admin_username}
              onChange={(e) => setForm({ ...form, admin_username: e.target.value })}
              placeholder="如 wy_yangguang"
            />
          </Field>
          <Field label="物业名称">
            <Input
              value={form.admin_name}
              onChange={(e) => setForm({ ...form, admin_name: e.target.value })}
              placeholder="如 阳光花园物业"
            />
          </Field>
          <Field label="初始密码（至少 8 位）">
            <Input
              required
              type="password"
              minLength={8}
              value={form.admin_password}
              onChange={(e) => setForm({ ...form, admin_password: e.target.value })}
            />
          </Field>
          <div className="col-span-2">
            <Button className="w-full" disabled={create.isPending}>
              {create.isPending ? "开通中…" : "开通小区"}
            </Button>
          </div>
        </form>
      </Modal>

      <Modal open={!!newPassword} onClose={() => setNewPassword(null)} title="密码已重置">
        <p className="mb-3 text-sm text-slate-600">
          新密码仅本次显示，请立即复制并发送给物业：
        </p>
        <div className="mb-4 flex items-center gap-2">
          <code className="flex-1 rounded-lg bg-slate-100 px-4 py-2.5 text-center text-base font-bold tracking-wider text-slate-800">
            {newPassword}
          </code>
          <Button
            variant="secondary"
            onClick={() => {
              navigator.clipboard.writeText(newPassword ?? "");
              toast.success("已复制");
            }}
          >
            <Copy size={14} />
          </Button>
        </div>
        <Button className="w-full" onClick={() => setNewPassword(null)}>
          我已保存
        </Button>
      </Modal>

      {/* 重置确认弹窗复用 resetFor 状态 */}
      {resetFor && (
        <Modal open={!!resetFor} onClose={() => setResetFor(null)} title="重置物业密码">
          <p className="mb-4 text-sm text-slate-600">
            确认重置「{resetFor.name}」的物业管理员密码？旧密码将立即失效。
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setResetFor(null)}>
              取消
            </Button>
            <Button variant="danger" onClick={() => resetPassword.mutate(resetFor.id)}>
              确认重置
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}
