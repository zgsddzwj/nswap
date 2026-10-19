import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Input";
import { api } from "@/lib/api";

export function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const qc = useQueryClient();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;
    setLoading(true);
    try {
      await api("POST", "/api/admin/auth/login", { username, password });
      qc.clear(); // 清掉登录前的 401 错误缓存
      toast.success("登录成功");
      navigate("/");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100">
      <div className="w-96 rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-brand text-lg font-bold text-white">
            n
          </div>
          <h1 className="text-lg font-bold text-slate-800">邻里汇 管理后台</h1>
          <p className="mt-1 text-sm text-slate-400">邻里汇小区服务 · 平台运营与物业管理</p>
        </div>
        <form onSubmit={submit} className="space-y-4">
          <Field label="用户名">
            <Input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus required />
          </Field>
          <Field label="密码">
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </Field>
          <Button className="w-full" disabled={loading}>
            {loading ? "登录中…" : "登录"}
          </Button>
        </form>
      </div>
    </div>
  );
}
