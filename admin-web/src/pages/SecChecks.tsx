import { useQuery } from "@tanstack/react-query";
import { api, type Page } from "@/lib/api";
import { Badge, Card, Empty, PageHeader } from "@/components/ui/Card";
import { fmtTime } from "@/lib/utils";

interface SecCheckRow {
  id: number;
  target_type: string;
  target_id: number | null;
  status: string;
  detail: Record<string, unknown> | null;
  created_at: string;
}

function StatusBadge({ status }: { status: string }) {
  if (status === "ok" || status === "pass") return <Badge tone="green">通过</Badge>;
  if (status === "risk") return <Badge tone="red">风险</Badge>;
  if (status === "error") return <Badge tone="amber">异常降级</Badge>;
  return <Badge tone="gray">处理中</Badge>;
}

export function SecChecks() {
  const { data } = useQuery({
    queryKey: ["sec-checks"],
    queryFn: () => api<Page<SecCheckRow>>("GET", "/api/admin/sec-checks?page=1&page_size=50"),
  });

  return (
    <div>
      <PageHeader title="内容安全记录" />
      <Card>
        {!data || data.list.length === 0 ? (
          <Empty text="暂无内容安全记录" />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs text-slate-400">
                <th className="px-5 py-2.5 font-medium">#</th>
                <th className="px-5 py-2.5 font-medium">类型</th>
                <th className="px-5 py-2.5 font-medium">对象</th>
                <th className="px-5 py-2.5 font-medium">状态</th>
                <th className="px-5 py-2.5 font-medium">详情</th>
                <th className="px-5 py-2.5 font-medium">时间</th>
              </tr>
            </thead>
            <tbody>
              {data.list.map((r) => (
                <tr key={r.id} className="border-b border-slate-50 last:border-0">
                  <td className="px-5 py-2.5 text-slate-400">{r.id}</td>
                  <td className="px-5 py-2.5">{r.target_type === "image" ? "图片" : "文本"}</td>
                  <td className="px-5 py-2.5 text-slate-500">{r.target_id ?? "-"}</td>
                  <td className="px-5 py-2.5">
                    <StatusBadge status={r.status} />
                  </td>
                  <td className="max-w-md px-5 py-2.5 text-slate-500">
                    <span className="line-clamp-1">{r.detail ? JSON.stringify(r.detail) : "-"}</span>
                  </td>
                  <td className="px-5 py-2.5 text-slate-500">{fmtTime(r.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
