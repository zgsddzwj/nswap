import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Input";
import { Card, PageHeader } from "@/components/ui/Card";

export function Password() {
  const [oldPassword, setOld] = useState("");
  const [newPassword, setNew] = useState("");
  const navigate = useNavigate();

  const change = useMutation({
    mutationFn: () => api("POST", "/api/admin/password", { old_password: oldPassword, new_password: newPassword }),
    onSuccess: () => {
      toast.success("密码已修改，请重新登录");
      navigate("/login");
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "修改失败"),
  });

  return (
    <div>
      <PageHeader title="修改密码" />
      <Card className="max-w-md p-5">
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            change.mutate();
          }}
        >
          <Field label="旧密码">
            <Input
              type="password"
              required
              value={oldPassword}
              onChange={(e) => setOld(e.target.value)}
            />
          </Field>
          <Field label="新密码（至少 8 位）">
            <Input
              type="password"
              required
              minLength={8}
              value={newPassword}
              onChange={(e) => setNew(e.target.value)}
            />
          </Field>
          <Button className="w-full" disabled={change.isPending}>
            {change.isPending ? "保存中…" : "保存"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
