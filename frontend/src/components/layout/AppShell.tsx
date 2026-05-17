import { Outlet } from "react-router-dom";
import { AppSidebar } from "./AppSidebar";
import { TopCommandBar } from "./TopCommandBar";

export function AppShell() {
  return (
    <div className="min-h-screen">
      <AppSidebar />
      <TopCommandBar />
      <main className="ml-72 mr-4 pb-10">
        <Outlet />
      </main>
    </div>
  );
}

