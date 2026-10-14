import { Navigate, NavLink, Outlet } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  BarChart3,
  Building2,
  Flag,
  KeyRound,
  LogOut,
  Megaphone,
  Package,
  ShieldCheck,
  Users,
} from "lucide-react";
import { useAdmin } from "@/lib/auth";
import { api } from "@/lib/api";

const NAV = [
  { to: "/admin", label: "看板", icon: BarChart3, end: true },
  { to: "/admin/invites", label: "邀请码管理", icon: KeyRound },
  { to: "/admin/announcements", label: "公告管理", icon: Megaphone },
  { to: "/admin/items", label: "内容巡查", icon: Package },
  { to: "/admin/reports", label: "举报处置", icon: Flag },
  { to: "/admin/users", label: "用户管理", icon: Users },
];

const SUPER_NAV = [
  { to: "/admin/communities", label: "小区管理", icon: Building2, end: false },
  { to: "/admin/sec-checks", label: "内容安全记录", icon: ShieldCheck, end: false },
];

export function AdminLayout() {
  const { data: admin, isLoading } = useAdmin();
  const qc = useQueryClient();

  if (isLoading) {
    return <div className="flex h-full items-center justify-center text-sm text-slate-400">加载中…</div>;
  }
  if (!admin) {
    return <Navigate to="/admin/login" replace />;
  }
  const isSuper = admin.role === "super";
  const communityLabel = isSuper ? "平台超管" : `物业管理员 · ${admin.community?.name ?? ""}`;

  async function logout() {
    try {
      await api("POST", "/api/admin/auth/logout");
    } finally {
      qc.clear();
      location.href = "/admin/login";
    }
  }

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-52 shrink-0 flex-col bg-slate-900 pt-4">
        <div className="border-b border-slate-700 px-4 pb-3">
          <div className="text-sm font-bold text-white">nswap 管理后台</div>
          <div className="mt-0.5 text-xs text-slate-500">{communityLabel}</div>
        </div>
        <nav className="flex-1 py-2">
          {[...NAV, ...(isSuper ? SUPER_NAV : [])].map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-2 px-4 py-2.5 text-sm ${
                  isActive
                    ? "bg-slate-800 text-white"
                    : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
                }`
              }
            >
              <item.icon size={15} />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-700 p-3">
          <button
            onClick={logout}
            className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-slate-600 py-1.5 text-xs text-slate-300 hover:bg-slate-800"
          >
            <LogOut size={13} /> 退出（{admin.name || admin.username}）
          </button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-6">
        <Outlet context={{ admin }} />
      </main>
    </div>
  );
}
