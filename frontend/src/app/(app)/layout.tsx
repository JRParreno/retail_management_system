import { redirect } from "next/navigation";

import { BranchProvider } from "@/components/branch/branch-context";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { getSessionUser } from "@/lib/auth";
import { Toaster } from "@/components/ui/sonner";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await getSessionUser();
  if (!user) redirect("/login");

  return (
    <BranchProvider user={user}>
      <div className="flex h-dvh max-h-dvh flex-col overflow-hidden lg:flex-row">
        <AppSidebar user={user} />
        <main className="min-h-0 min-w-0 flex-1 overflow-y-auto overscroll-contain">
          <div className="mx-auto w-full max-w-7xl p-3 sm:p-4 lg:p-6">
            {children}
          </div>
        </main>
        <Toaster richColors position="top-center" />
      </div>
    </BranchProvider>
  );
}
