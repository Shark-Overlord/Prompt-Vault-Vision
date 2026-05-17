import { useState } from "react";
import { Database, Github, ShieldCheck, ShieldOff } from "lucide-react";
import { useGithubAuth } from "../../hooks/useGithubAuth";
import { GithubConnectDialog } from "../auth/GithubConnectDialog";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";

export function TopCommandBar() {
  const [authOpen, setAuthOpen] = useState(false);
  const { data: auth, isLoading } = useGithubAuth();
  const connected = Boolean(auth?.connected);

  return (
    <>
      <header className="mb-6 ml-72 mr-4">
        <Card className="flex min-h-16 flex-row items-center justify-between gap-3 p-4">
          <div className="flex items-center gap-3">
            <Badge variant="secondary" className="gap-2 px-3 py-1.5">
              <Database className="h-3.5 w-3.5" />
              本地 SQLite 已连接
            </Badge>
            <Badge variant={connected ? "secondary" : "outline"} className="gap-2 px-3 py-1.5">
              {connected ? <ShieldCheck className="h-3.5 w-3.5" /> : <ShieldOff className="h-3.5 w-3.5" />}
              {isLoading ? "GitHub 检测中" : connected ? `GitHub 已连接${auth?.login ? `：${auth.login}` : ""}` : "GitHub 未连接"}
            </Badge>
          </div>
          <Button variant={connected ? "outline" : "default"} onClick={() => setAuthOpen(true)}>
            <Github className="h-4 w-4" />
            {connected ? "管理连接" : "连接 GitHub"}
          </Button>
        </Card>
      </header>
      <GithubConnectDialog open={authOpen} onClose={() => setAuthOpen(false)} />
    </>
  );
}
