import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { api, type Page } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Badge, Card, Empty, PageHeader } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { fmtTime } from "@/lib/utils";

interface ReportRow {
  id: number;
  target_type: string;
  target_id: number;
  target_text: string;
  reason: string;
  detail: string | null;
  status: string;
  note: string | null;
  community_id: number | null;
  community_name: string;
  reporter: { id: number; nickname: string | null };
  created_at: string;
  handled_at: string | null;
}

const TYPE_LABEL: Record<string, string> = { item: "物品", message: "留言", user: "用户" };

function StatusBadge({ status }: { status: string }) {
  if (status === "pending") return <Badge tone="amber">待处理</Badge>;
  if (status === "resolved") return <Badge tone="green">已处置</Badge>;
  return <Badge tone="gray">已驳回</Badge>;
}

export function Reports() {
  const qc = useQueryClient();
  const [status, setStatus] = useState("pending");
  const [page, setPage] = useState(1);
  const [handling, setHandling] = useState<ReportRow | null>(null);
  const [applyAction, setApplyAction] = useState(false);
  const [note, setNote] = useState("");

  const { data } = useQuery({
    queryKey: ["reports", status, page],
    queryFn: () =>
      api<Page<ReportRow>>(
        "GET",
        `/api/admin/reports?page=${page}&page_size=20${status ? `&status=${status}` : ""}`
      ),
  });

  const handle = useMutation({
    mutationFn: (v: { id: number; decision: "resolve" | "dismiss" }) =>
      api("POST", `/api/admin/reports/${v.id}`, { decision: v.decision, apply_action: applyAction, note }),
    onSuccess: () => {
      toast.success("已处理");
      setHandling(null);
      setApplyAction(false);
      setNote("");
      qc.invalidateQueries({ queryKey: ["reports"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "操作失败"),
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / 20)) : 1;

  return (
    <div>
      <PageHeader title="举报处置" />
      <div className="mb-4 flex gap-2">
        {[
          ["pending", "待处理"],
          ["resolved", "已处置"],
          ["dismissed", "已驳回"],
          ["", "全部"],
        ].map(([v, l]) => (
          <button
            key={v}
            onClick={() => {
              setStatus(v);
              setPage(1);
            }}
            className={`rounded-full px-3.5 py-1.5 text-sm font-medium ${
              status === v ? "bg-brand text-white" : "bg-white text-slate-500 hover:bg-slate-100"
            }`}
          >
            {l}
          </button>
        ))}
      </div>

      {!data || data.list.length === 0 ? (
        <Card>
          <Empty text="没有符合条件的举报" />
        </Card>
      ) : (
        <div className="space-y-3">
          {data.list.map((r) => (
            <Card key={r.id} className="p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="blue">{TYPE_LABEL[r.target_type] ?? r.target_type}</Badge>
                    <span className="text-xs text-slate-400">{r.community_name}</span>
                    <span className="text-sm font-medium text-slate-700">{r.target_text}</span>
                    <span className="text-sm font-semibold text-[var(--color-danger)]">{r.reason}</span>
                    <StatusBadge status={r.status} />
                  </div>
                  {r.detail && <div className="mt-1.5 text-sm text-slate-500">{r.detail}</div>}
                  <div className="mt-1.5 text-xs text-slate-400">
                    举报人 #{r.reporter.id} {r.reporter.nickname ?? ""} · {fmtTime(r.created_at)}
                    {r.handled_at ? ` · 处理于 ${fmtTime(r.handled_at)}` : ""}
                    {r.note ? ` · 备注：${r.note}` : ""}
                  </div>
                </div>
                {r.status === "pending" && (
                  <Button
                    className="shrink-0"
                    onClick={() => {
                      setHandling(r);
                      setApplyAction(false);
                      setNote("");
                    }}
                  >
                    去处置
                  </Button>
                )}
              </div>
            </Card>
          ))}
          {data.total > 20 && (
            <div className="flex items-center justify-between text-sm text-slate-500">
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
        </div>
      )}

      <Modal open={!!handling} onClose={() => setHandling(null)} title="举报处置">
        <p className="mb-1 text-sm text-slate-600">{handling?.target_text}</p>
        <p className="mb-4 text-sm">
          原因：<span className="font-semibold text-[var(--color-danger)]">{handling?.reason}</span>
          {handling?.detail && <span className="text-slate-500">（{handling.detail}）</span>}
        </p>
        <label className="mb-4 flex items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={applyAction}
            onChange={(e) => setApplyAction(e.target.checked)}
            className="h-4 w-4 rounded border-slate-300"
          />
          同时执行处置（下架物品/隐藏留言/封禁用户）
        </label>
        <textarea
          className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand focus:outline-none"
          rows={2}
          placeholder="处理备注（选填）"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <div className="flex justify-end gap-2">
          <Button
            variant="secondary"
            onClick={() => handling && handle.mutate({ id: handling.id, decision: "dismiss" })}
          >
            驳回
          </Button>
          <Button
            variant="danger"
            disabled={handle.isPending}
            onClick={() => handling && handle.mutate({ id: handling.id, decision: "resolve" })}
          >
            {handle.isPending ? "处理中…" : "确认处置"}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
