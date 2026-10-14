import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Badge, Card, CardHeader, Empty, PageHeader } from "@/components/ui/Card";
import { fmtTime } from "@/lib/utils";

interface PendingItem {
  id: number;
  title: string;
  author_nickname: string | null;
  community_name: string;
  created_at: string;
}

interface PendingMessage {
  id: number;
  content: string;
  item_id: number;
  item_title: string | null;
  author_nickname: string | null;
  created_at: string;
}

interface PendingData {
  items: PendingItem[];
  items_total: number;
  messages: PendingMessage[];
  messages_total: number;
}

export function PendingContent() {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["pending-content"],
    queryFn: () => api<PendingData>("GET", "/api/admin/pending-content?page=1&page_size=50"),
  });

  const handle = useMutation({
    mutationFn: (v: { kind: "item" | "message"; id: number; decision: "approve" | "reject" }) =>
      api("POST", `/api/admin/pending-content/${v.kind}/${v.id}/${v.decision}`),
    onSuccess: (_d, v) => {
      toast.success(v.decision === "approve" ? "已放行" : "已拒绝并通知作者");
      qc.invalidateQueries({ queryKey: ["pending-content"] });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "操作失败"),
  });

  const total = (data?.items_total ?? 0) + (data?.messages_total ?? 0);

  return (
    <div>
      <PageHeader title="内容审核">
        {total > 0 && <Badge tone="amber">待处理 {total} 条</Badge>}
      </PageHeader>
      <p className="mb-4 text-sm text-slate-500">
        自动内容审核接口异常时，内容会降级为「待审」状态（仅作者与管理员可见）。请人工判断后放行或拒绝。
      </p>

      <Card className="mb-5">
        <CardHeader title={`待审物品（${data?.items_total ?? 0}）`} />
        {!data || data.items.length === 0 ? (
          <Empty text="没有待审物品" />
        ) : (
          <table className="w-full text-sm">
            <tbody>
              {data.items.map((it) => (
                <tr key={it.id} className="border-b border-slate-50 last:border-0">
                  <td className="px-5 py-3 font-medium text-slate-700">{it.title}</td>
                  <td className="px-5 py-3 text-slate-500">
                    {it.author_nickname} · {it.community_name}
                  </td>
                  <td className="px-5 py-3 text-slate-400">{fmtTime(it.created_at)}</td>
                  <td className="px-5 py-3">
                    <div className="flex gap-2">
                      <Button
                        className="px-2.5 py-1 text-xs"
                        onClick={() => handle.mutate({ kind: "item", id: it.id, decision: "approve" })}
                      >
                        放行
                      </Button>
                      <Button
                        variant="danger"
                        className="px-2.5 py-1 text-xs"
                        onClick={() => handle.mutate({ kind: "item", id: it.id, decision: "reject" })}
                      >
                        拒绝并下架
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card>
        <CardHeader title={`待审留言（${data?.messages_total ?? 0}）`} />
        {!data || data.messages.length === 0 ? (
          <Empty text="没有待审留言" />
        ) : (
          <table className="w-full text-sm">
            <tbody>
              {data.messages.map((m) => (
                <tr key={m.id} className="border-b border-slate-50 last:border-0">
                  <td className="max-w-md px-5 py-3 text-slate-700">{m.content}</td>
                  <td className="px-5 py-3 text-slate-500">
                    {m.author_nickname} · 于「{m.item_title ?? `物品#${m.item_id}`}」
                  </td>
                  <td className="px-5 py-3 text-slate-400">{fmtTime(m.created_at)}</td>
                  <td className="px-5 py-3">
                    <div className="flex gap-2">
                      <Button
                        className="px-2.5 py-1 text-xs"
                        onClick={() => handle.mutate({ kind: "message", id: m.id, decision: "approve" })}
                      >
                        放行
                      </Button>
                      <Button
                        variant="danger"
                        className="px-2.5 py-1 text-xs"
                        onClick={() => handle.mutate({ kind: "message", id: m.id, decision: "reject" })}
                      >
                        拒绝并隐藏
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
