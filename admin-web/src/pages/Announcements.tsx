import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { api, type AdminInfo, type Page } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Input";
import { Card, Empty, PageHeader } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { fmtTime } from "@/lib/utils";

interface AnnouncementRow {
  id: number;
  title: string;
  content: string;
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

export function Announcements() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [publishOpen, setPublishOpen] = useState(false);
  const [deleting, setDeleting] = useState<AnnouncementRow | null>(null);
  const { data: admin } = useQuery({
    queryKey: ["me"],
    queryFn: () => api<AdminInfo>("GET", "/api/admin/auth/me"),
    staleTime: 60_000,
  });
  const isSuper = admin?.role === "super";

  const { data } = useQuery({
    queryKey: ["announcements", page],
    queryFn: () => api<Page<AnnouncementRow>>("GET", `/api/admin/announcements?page=${page}&page_size=20`),
  });
  const communities = useQuery({
    queryKey: ["communities-lite"],
    queryFn: () => api<{ list: CommunityRow[] }>("GET", "/api/admin/communities"),
    enabled: !!isSuper,
  });

  const [form, setForm] = useState({ title: "", content: "", community_id: 0 });
  const publish = useMutation({
    mutationFn: () =>
      api("POST", "/api/admin/announcements", {
        title: form.title,
        content: form.content,
        community_id: isSuper ? form.community_id || null : null,
      }),
    onSuccess: () => {
      toast.success("公告已发布");
      setPublishOpen(false);
      setForm({ title: "", content: "", community_id: 0 });
      qc.invalidateQueries({ queryKey: ["announcements"] });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "发布失败"),
  });

  const remove = useMutation({
    mutationFn: (id: number) => api("DELETE", `/api/admin/announcements/${id}`),
    onSuccess: () => {
      toast.success("已删除");
      setDeleting(null);
      qc.invalidateQueries({ queryKey: ["announcements"] });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "操作失败"),
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / 20)) : 1;

  return (
    <div>
      <PageHeader title="公告管理">
        <Button onClick={() => setPublishOpen(true)}>发布公告</Button>
      </PageHeader>

      <Card>
        {!data || data.list.length === 0 ? (
          <Empty text="还没有发布公告" />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs text-slate-400">
                <th className="px-5 py-2.5 font-medium">#</th>
                {isSuper && <th className="px-5 py-2.5 font-medium">小区</th>}
                <th className="px-5 py-2.5 font-medium">标题</th>
                <th className="px-5 py-2.5 font-medium">正文</th>
                <th className="px-5 py-2.5 font-medium">发布人</th>
                <th className="px-5 py-2.5 font-medium">时间</th>
                <th className="px-5 py-2.5"></th>
              </tr>
            </thead>
            <tbody>
              {data.list.map((a) => (
                <tr key={a.id} className="border-b border-slate-50 last:border-0">
                  <td className="px-5 py-2.5 text-slate-400">{a.id}</td>
                  {isSuper && <td className="px-5 py-2.5 text-slate-500">{a.community_name}</td>}
                  <td className="px-5 py-2.5 font-medium text-slate-700">{a.title}</td>
                  <td className="max-w-xs px-5 py-2.5 text-slate-500">
                    <span className="line-clamp-1">{a.content}</span>
                  </td>
                  <td className="px-5 py-2.5 text-slate-500">{a.published_by_name || "-"}</td>
                  <td className="px-5 py-2.5 text-slate-500">{fmtTime(a.created_at)}</td>
                  <td className="px-5 py-2.5">
                    <Button
                      variant="outline"
                      className="px-2.5 py-1 text-xs"
                      onClick={() => setDeleting(a)}
                    >
                      删除
                    </Button>
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

      <Modal open={publishOpen} onClose={() => setPublishOpen(false)} title="发布公告">
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            publish.mutate();
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
          <Field label="标题（≤100 字）">
            <Input
              required
              maxLength={100}
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="如：本周六小区闲置交换日"
            />
          </Field>
          <Field label="正文">
            <Textarea
              required
              rows={4}
              value={form.content}
              onChange={(e) => setForm({ ...form, content: e.target.value })}
              placeholder="公告内容，仅本小区住户可见"
            />
          </Field>
          <Button className="w-full" disabled={publish.isPending}>
            {publish.isPending ? "发布中…" : "发布公告"}
          </Button>
        </form>
      </Modal>

      <Modal open={!!deleting} onClose={() => setDeleting(null)} title="删除公告">
        <p className="mb-4 text-sm text-slate-600">
          确认删除「{deleting?.title}」？删除后住户端立即不可见。
        </p>
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
