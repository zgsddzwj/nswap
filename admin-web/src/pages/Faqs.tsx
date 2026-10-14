import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { api, type AdminInfo, type Page } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Input";
import { Card, Empty, PageHeader } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { fmtTime } from "@/lib/utils";

interface FaqRow {
  id: number;
  title: string;
  content: string;
  pinned: boolean;
  like_count: number;
  community_id: number;
  community_name: string;
  published_by_name: string | null;
  created_at: string;
}

interface CommunityRow {
  id: number;
  name: string;
  city: string;
  status: string;
}

export function Faqs() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<FaqRow | null>(null);
  const [deleting, setDeleting] = useState<FaqRow | null>(null);
  const [form, setForm] = useState({ title: "", content: "", pinned: false, community_id: 0 });
  const { data: admin } = useQuery({
    queryKey: ["me"],
    queryFn: () => api<AdminInfo>("GET", "/api/admin/auth/me"),
    staleTime: 60_000,
  });
  const isSuper = admin?.role === "super";

  const { data } = useQuery({
    queryKey: ["faqs", page],
    queryFn: () => api<Page<FaqRow>>("GET", `/api/admin/faqs?page=${page}&page_size=20`),
  });
  const communities = useQuery({
    queryKey: ["communities-lite"],
    queryFn: () => api<{ list: CommunityRow[] }>("GET", "/api/admin/communities"),
    enabled: !!isSuper,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["faqs"] });

  const create = useMutation({
    mutationFn: () =>
      api<{ id: number }>("POST", "/api/admin/faq", {
        ...form,
        community_id: isSuper ? form.community_id || null : null,
      }),
    onSuccess: () => {
      toast.success("FAQ 已发布");
      setCreateOpen(false);
      setForm({ title: "", content: "", pinned: false, community_id: 0 });
      invalidate();
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "发布失败"),
  });

  const update = useMutation({
    mutationFn: (id: number) =>
      api("PUT", `/api/admin/faq/${id}`, {
        title: form.title,
        content: form.content,
        pinned: form.pinned,
      }),
    onSuccess: () => {
      toast.success("已保存");
      setEditing(null);
      invalidate();
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "保存失败"),
  });

  const togglePin = useMutation({
    mutationFn: (a: FaqRow) => api("PUT", `/api/admin/faq/${a.id}`, { pinned: !a.pinned }),
    onSuccess: () => invalidate(),
    onError: (e) => toast.error(e instanceof Error ? e.message : "操作失败"),
  });

  const remove = useMutation({
    mutationFn: (id: number) => api("DELETE", `/api/admin/faq/${id}`),
    onSuccess: () => {
      toast.success("已删除");
      setDeleting(null);
      invalidate();
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "操作失败"),
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / 20)) : 1;

  return (
    <div>
      <PageHeader title="FAQ 管理">
        <Button onClick={() => setCreateOpen(true)}>发布常见问题</Button>
      </PageHeader>
      <p className="mb-4 text-sm text-slate-500">
        常见问题会在小程序「邻里 FAQ」页置顶展示，住户可点赞；免内容审核（管理端可信发布）。
      </p>

      <Card>
        {!data || data.list.length === 0 ? (
          <Empty text="还没有发布 FAQ" />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs text-slate-400">
                <th className="px-5 py-2.5 font-medium">#</th>
                {isSuper && <th className="px-5 py-2.5 font-medium">小区</th>}
                <th className="px-5 py-2.5 font-medium">问题</th>
                <th className="px-5 py-2.5 font-medium">答案</th>
                <th className="px-5 py-2.5 font-medium">点赞</th>
                <th className="px-5 py-2.5 font-medium">发布人</th>
                <th className="px-5 py-2.5 font-medium">时间</th>
                <th className="px-5 py-2.5"></th>
              </tr>
            </thead>
            <tbody>
              {data.list.map((f) => (
                <tr key={f.id} className="border-b border-slate-50 last:border-0">
                  <td className="px-5 py-2.5 text-slate-400">{f.id}</td>
                  {isSuper && <td className="px-5 py-2.5 text-slate-500">{f.community_name}</td>}
                  <td className="px-5 py-2.5 font-medium text-slate-700">
                    {f.pinned && (
                      <span className="mr-1.5 rounded bg-amber-50 px-1.5 py-0.5 text-xs text-amber-700">置顶</span>
                    )}
                    {f.title}
                  </td>
                  <td className="max-w-xs px-5 py-2.5 text-slate-500">
                    <span className="line-clamp-1">{f.content}</span>
                  </td>
                  <td className="px-5 py-2.5">{f.like_count}</td>
                  <td className="px-5 py-2.5 text-slate-500">{f.published_by_name || "-"}</td>
                  <td className="px-5 py-2.5 text-slate-500">{fmtTime(f.created_at)}</td>
                  <td className="px-5 py-2.5">
                    <div className="flex gap-1.5">
                      <Button
                        variant="outline"
                        className="px-2 py-1 text-xs"
                        onClick={() => {
                          setEditing(f);
                          setForm({ ...form, title: f.title, content: f.content, pinned: f.pinned });
                        }}
                      >
                        编辑
                      </Button>
                      <Button
                        variant="secondary"
                        className="px-2 py-1 text-xs"
                        onClick={() => togglePin.mutate(f)}
                      >
                        {f.pinned ? "取消置顶" : "置顶"}
                      </Button>
                      <Button
                        variant="outline"
                        className="px-2 py-1 text-xs"
                        onClick={() => setDeleting(f)}
                      >
                        删除
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

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="发布常见问题">
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          {isSuper && (
            <Field label="目标小区">
              <Select
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
          <Field label="问题（≤50 字）">
            <Input
              required
              maxLength={50}
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="如：交换的物品质量有问题怎么办？"
            />
          </Field>
          <Field label="答案">
            <Textarea
              required
              rows={4}
              value={form.content}
              onChange={(e) => setForm({ ...form, content: e.target.value })}
              placeholder="请当面验货、钱货两清；如遇问题可联系楼长调解…"
            />
          </Field>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={form.pinned}
              onChange={(e) => setForm({ ...form, pinned: e.target.checked })}
              className="h-4 w-4 rounded border-slate-300"
            />
            在邻里 FAQ 页置顶
          </label>
          <Button className="w-full" disabled={create.isPending}>
            {create.isPending ? "发布中…" : "发布"}
          </Button>
        </form>
      </Modal>

      <Modal open={!!editing} onClose={() => setEditing(null)} title="编辑 FAQ">
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (editing) update.mutate(editing.id);
          }}
        >
          <Field label="问题（≤50 字）">
            <Input
              required
              maxLength={50}
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
          </Field>
          <Field label="答案">
            <Textarea
              required
              rows={4}
              value={form.content}
              onChange={(e) => setForm({ ...form, content: e.target.value })}
            />
          </Field>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={form.pinned}
              onChange={(e) => setForm({ ...form, pinned: e.target.checked })}
              className="h-4 w-4 rounded border-slate-300"
            />
            置顶
          </label>
          <Button className="w-full" disabled={update.isPending}>
            {update.isPending ? "保存中…" : "保存"}
          </Button>
        </form>
      </Modal>

      <Modal open={!!deleting} onClose={() => setDeleting(null)} title="删除 FAQ">
        <p className="mb-4 text-sm text-slate-600">确认删除「{deleting?.title}」？住户端立即不可见。</p>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setDeleting(null)}>
            取消
          </Button>
          <Button variant="danger" onClick={() => deleting && remove.mutate(deleting.id)}>
            确认删除
          </Button>
        </div>
      </Modal>
    </div>
  );
}
