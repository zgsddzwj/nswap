import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { api, type Page } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Input";
import { Badge, Card, Empty, PageHeader } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { fmtTime } from "@/lib/utils";

interface ItemRow {
  id: number;
  title: string;
  type: string;
  status: string;
  building: string;
  owner_nickname: string | null;
  community_id: number;
  community_name: string;
  created_at: string;
}

const TYPE_LABEL: Record<string, string> = {
  sell: "出售",
  give: "赠送",
  swap: "换物",
  want: "求购",
};

const STATUS_LABEL: Record<string, string> = {
  on_sale: "在架",
  reserved: "已预约",
  completed: "已完成",
  archived: "已归档",
  sunk: "已沉底",
};

function StatusBadge({ status }: { status: string }) {
  const tone =
    status === "on_sale" ? "green" : status === "reserved" ? "amber" : status === "completed" ? "blue" : "gray";
  return <Badge tone={tone as "green" | "amber" | "blue" | "gray"}>{STATUS_LABEL[status] ?? status}</Badge>;
}

export function Items() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({ status: "", type: "", keyword: "" });
  const [offTarget, setOffTarget] = useState<ItemRow | null>(null);
  const isSuper = false; // 小区列展示由数据决定；超管看全部小区名

  const { data } = useQuery({
    queryKey: ["admin-items", page, filters],
    queryFn: () => {
      const params = new URLSearchParams({ page: String(page), page_size: "20" });
      if (filters.status) params.set("status", filters.status);
      if (filters.type) params.set("type", filters.type);
      if (filters.keyword) params.set("keyword", filters.keyword);
      return api<Page<ItemRow>>("GET", `/api/admin/items?${params.toString()}`);
    },
  });

  const off = useMutation({
    mutationFn: (id: number) => api("POST", `/api/admin/items/${id}/off`),
    onSuccess: () => {
      toast.success("已强制下架");
      setOffTarget(null);
      qc.invalidateQueries({ queryKey: ["admin-items"] });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "操作失败"),
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / 20)) : 1;
  const showCommunityCol = (data?.list ?? []).some((x) => x.community_name);

  return (
    <div>
      <PageHeader title="内容巡查" />

      <Card className="mb-5 p-4">
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            setPage(1);
            qc.invalidateQueries({ queryKey: ["admin-items"] });
          }}
        >
          <Select
            className="w-32"
            value={filters.status}
            onChange={(e) => {
              setFilters({ ...filters, status: e.target.value });
              setPage(1);
            }}
          >
            <option value="">全部状态</option>
            {Object.entries(STATUS_LABEL).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </Select>
          <Select
            className="w-28"
            value={filters.type}
            onChange={(e) => {
              setFilters({ ...filters, type: e.target.value });
              setPage(1);
            }}
          >
            <option value="">全部形态</option>
            {Object.entries(TYPE_LABEL).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </Select>
          <Input
            className="w-56"
            placeholder="按标题搜索"
            value={filters.keyword}
            onChange={(e) => setFilters({ ...filters, keyword: e.target.value })}
          />
          <Button variant="secondary">查询</Button>
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
                <th className="px-5 py-2.5 font-medium">标题</th>
                <th className="px-5 py-2.5 font-medium">形态</th>
                <th className="px-5 py-2.5 font-medium">状态</th>
                <th className="px-5 py-2.5 font-medium">发布人</th>
                {(isSuper || showCommunityCol) && <th className="px-5 py-2.5 font-medium">小区</th>}
                <th className="px-5 py-2.5 font-medium">时间</th>
                <th className="px-5 py-2.5"></th>
              </tr>
            </thead>
            <tbody>
              {data.list.map((it) => (
                <tr key={it.id} className="border-b border-slate-50 last:border-0">
                  <td className="px-5 py-2.5 text-slate-400">{it.id}</td>
                  <td className="max-w-xs px-5 py-2.5 font-medium text-slate-700">
                    <span className="line-clamp-1">{it.title}</span>
                  </td>
                  <td className="px-5 py-2.5">{TYPE_LABEL[it.type] ?? it.type}</td>
                  <td className="px-5 py-2.5">
                    <StatusBadge status={it.status} />
                  </td>
                  <td className="px-5 py-2.5 text-slate-500">{it.owner_nickname || "-"}</td>
                  {(isSuper || showCommunityCol) && (
                    <td className="px-5 py-2.5 text-slate-500">{it.community_name}</td>
                  )}
                  <td className="px-5 py-2.5 text-slate-500">{fmtTime(it.created_at)}</td>
                  <td className="px-5 py-2.5">
                    {(it.status === "on_sale" || it.status === "sunk") && (
                      <Button
                        variant="outline"
                        className="px-2.5 py-1 text-xs"
                        onClick={() => setOffTarget(it)}
                      >
                        强制下架
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

      <Modal open={!!offTarget} onClose={() => setOffTarget(null)} title="强制下架">
        <p className="mb-4 text-sm text-slate-600">
          确认强制下架「{offTarget?.title}」？物品将归档，住户端不可见。
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setOffTarget(null)}>
            取消
          </Button>
          <Button variant="danger" onClick={() => offTarget && off.mutate(offTarget.id)}>
            确认下架
          </Button>
        </div>
      </Modal>
    </div>
  );
}
