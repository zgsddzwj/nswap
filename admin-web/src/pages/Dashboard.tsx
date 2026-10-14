import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/Card";

interface Stats {
  users: number;
  verified: number;
  items: number;
  trades_done: number;
  pending_reports: number;
  pending_verify: number;
  active_invites: number;
  communities_overview?: {
    id: number;
    name: string;
    city: string;
    status: string;
    users: number;
    items: number;
    admins: number;
  }[];
}

export function Dashboard() {
  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: () => api<Stats>("GET", "/api/admin/stats"),
  });
  if (!stats) return <div className="text-sm text-slate-400">加载中…</div>;

  const cards: [string, number][] = [
    ["注册用户", stats.users],
    ["已验证住户", stats.verified],
    ["在架物品", stats.items],
    ["完成交易", stats.trades_done],
    ["待处理举报", stats.pending_reports],
    ["待审验证", stats.pending_verify],
    ["可用邀请码", stats.active_invites],
  ];

  return (
    <div>
      <h1 className="mb-5 text-lg font-bold text-slate-800">数据看板</h1>
      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
        {cards.map(([label, value]) => (
          <Card key={label} className="p-4 text-center">
            <div className="text-2xl font-bold text-slate-800">{value}</div>
            <div className="mt-1 text-xs text-slate-400">{label}</div>
          </Card>
        ))}
      </div>

      {stats.communities_overview && (
        <Card>
          <div className="border-b border-slate-100 px-5 py-3.5 text-sm font-semibold text-slate-800">
            小区概览
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs text-slate-400">
                <th className="px-5 py-2.5 font-medium">#</th>
                <th className="px-5 py-2.5 font-medium">小区</th>
                <th className="px-5 py-2.5 font-medium">城市</th>
                <th className="px-5 py-2.5 font-medium">状态</th>
                <th className="px-5 py-2.5 font-medium">住户</th>
                <th className="px-5 py-2.5 font-medium">在架物品</th>
                <th className="px-5 py-2.5 font-medium">物业账号</th>
              </tr>
            </thead>
            <tbody>
              {stats.communities_overview.map((c) => (
                <tr key={c.id} className="border-b border-slate-50 last:border-0">
                  <td className="px-5 py-2.5 text-slate-400">{c.id}</td>
                  <td className="px-5 py-2.5 font-medium text-slate-700">{c.name}</td>
                  <td className="px-5 py-2.5 text-slate-500">{c.city}</td>
                  <td className="px-5 py-2.5">
                    {c.status === "active" ? (
                      <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700">正常</span>
                    ) : (
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">已停用</span>
                    )}
                  </td>
                  <td className="px-5 py-2.5">{c.users}</td>
                  <td className="px-5 py-2.5">{c.items}</td>
                  <td className="px-5 py-2.5">{c.admins}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
