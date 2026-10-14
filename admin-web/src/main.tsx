import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import "./index.css";
import { AdminLayout } from "@/components/layout/AdminLayout";
import { Login } from "@/pages/Login";
import { Dashboard } from "@/pages/Dashboard";
import { Invites } from "@/pages/Invites";
import { Announcements } from "@/pages/Announcements";
import { Items } from "@/pages/Items";
import { Reports } from "@/pages/Reports";
import { Users } from "@/pages/Users";
import { Communities } from "@/pages/Communities";
import { SecChecks } from "@/pages/SecChecks";
import { Password } from "@/pages/Password";

const qc = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <BrowserRouter basename="/admin">
        <Routes>
          <Route path="login" element={<Login />} />
          <Route element={<AdminLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="invites" element={<Invites />} />
            <Route path="announcements" element={<Announcements />} />
            <Route path="items" element={<Items />} />
            <Route path="reports" element={<Reports />} />
            <Route path="users" element={<Users />} />
            <Route path="communities" element={<Communities />} />
            <Route path="sec-checks" element={<SecChecks />} />
            <Route path="password" element={<Password />} />
          </Route>
          <Route path="*" element={<Navigate to="/admin" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-center" richColors />
    </QueryClientProvider>
  </React.StrictMode>
);
