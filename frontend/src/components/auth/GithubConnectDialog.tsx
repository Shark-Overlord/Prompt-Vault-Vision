import { useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle2, Copy, ExternalLink, Github, Loader2, LogOut, ShieldAlert } from "lucide-react";
import { useGithubAuth, useLogoutGithub, usePollGithubDevice, useSaveGithubClientId, useStartGithubDevice } from "../../hooks/useGithubAuth";
import type { GithubDeviceStart } from "../../lib/types";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "../ui/dialog";
import { Input } from "../ui/input";

export function GithubConnectDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { data: auth, refetch: refetchAuth } = useGithubAuth();
  const saveClient = useSaveGithubClientId();
  const startDevice = useStartGithubDevice();
  const pollDevice = usePollGithubDevice();
  const logout = useLogoutGithub();
  const [clientId, setClientId] = useState("");
  const [device, setDevice] = useState<GithubDeviceStart | null>(null);
  const [message, setMessage] = useState("");
  const [polling, setPolling] = useState(false);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    if (auth?.client_id && !clientId) setClientId(auth.client_id);
  }, [auth?.client_id, clientId]);

  useEffect(() => {
    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
  }, []);

  const authUrl = useMemo(() => device?.verification_uri_complete || device?.verification_uri, [device]);

  useEffect(() => {
    if (!polling || !device) return;
    let stopped = false;

    const stopPolling = (nextMessage?: string) => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
      timerRef.current = null;
      setPolling(false);
      if (nextMessage) setMessage(nextMessage);
    };

    const run = async () => {
      try {
        const result = await pollDevice.mutateAsync({ session_id: device.session_id });
        if (stopped) return;

        setMessage(result.message || "");
        if (result.status === "connected") {
          await refetchAuth();
          stopPolling("GitHub 已连接，后续增量搜索会自动使用本地 token。");
          setDevice(null);
          return;
        }

        if (result.status === "expired") {
          stopPolling(result.message || "授权会话已过期，请重新连接 GitHub。");
          return;
        }

        if (result.status === "error") {
          stopPolling(result.message || "GitHub 授权失败，请重新开始连接。");
          return;
        }

        const nextInterval = Math.max(result.interval || device.interval || 5, 3);
        timerRef.current = window.setTimeout(run, nextInterval * 1000);
      } catch (error) {
        if (stopped) return;
        stopPolling(error instanceof Error ? `轮询失败：${error.message}` : "轮询失败，请重新开始连接。");
      }
    };

    timerRef.current = window.setTimeout(run, 1000);
    return () => {
      stopped = true;
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
  }, [device, polling]);

  const save = async () => {
    try {
      await saveClient.mutateAsync({ client_id: clientId.trim() });
      setMessage("Client ID 已保存到本地凭据文件。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Client ID 保存失败。");
    }
  };

  const start = async () => {
    if (!clientId.trim() && !auth?.configured) {
      setMessage("请先填写 GitHub OAuth App 的 Client ID。需要在 GitHub Developer settings 创建 OAuth App，并启用 Device Flow。");
      return;
    }
    try {
      if (timerRef.current) window.clearTimeout(timerRef.current);
      const response = await startDevice.mutateAsync({ client_id: clientId.trim() || undefined, scope: "read:user" });
      setDevice(response);
      setMessage("请在 GitHub 页面完成授权。授权完成后，本弹窗会自动检测连接结果。");
      setPolling(true);
      window.open(response.verification_uri_complete || response.verification_uri, "_blank", "noopener,noreferrer");
    } catch (error) {
      setPolling(false);
      setMessage(error instanceof Error ? error.message : "GitHub 授权启动失败。");
    }
  };

  const stopWaiting = () => {
    if (timerRef.current) window.clearTimeout(timerRef.current);
    timerRef.current = null;
    setPolling(false);
    setMessage("已停止等待授权结果。可以点击“重新开始”发起新的 GitHub 授权。");
  };

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-lg border bg-muted">
              <Github className="h-5 w-5" />
            </div>
            <div>
              <DialogTitle>连接 GitHub</DialogTitle>
              <DialogDescription>Device Flow 授权，token 只保存在本地后端。</DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-5">
          {auth?.connected ? (
            <div className="rounded-xl border bg-muted/40 p-4">
              <div className="flex items-center gap-3">
                {auth.avatar_url && <img src={auth.avatar_url} className="h-10 w-10 rounded-lg" />}
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <CheckCircle2 className="h-4 w-4" />
                    已连接 {auth.login || "GitHub"}
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">来源：{auth.source}；权限：{auth.scope || "unknown"}</div>
                </div>
              </div>
              <div className="mt-4 flex gap-2">
                {auth.html_url && (
                  <Button variant="outline" onClick={() => window.open(auth.html_url, "_blank")}>
                    <ExternalLink className="h-4 w-4" />
                    打开 GitHub
                  </Button>
                )}
                <Button variant="destructive" onClick={() => logout.mutate()}>
                  <LogOut className="h-4 w-4" />
                  断开本地连接
                </Button>
              </div>
            </div>
          ) : (
            <>
              <div className="rounded-xl border bg-muted/40 p-4 text-sm leading-6">
                <div className="flex items-center gap-2 font-medium">
                  <ShieldAlert className="h-4 w-4" />
                  需要 GitHub OAuth App Client ID
                </div>
                <p className="mt-2 text-muted-foreground">
                  第一次使用时，请在 GitHub 创建 OAuth App 并启用 Device Flow，把 Client ID 填到这里。后续点击连接即可自动获取 token。
                </p>
              </div>
              <div>
                <label className="mb-2 block text-xs text-muted-foreground">GitHub OAuth App Client ID</label>
                <div className="flex gap-2">
                  <Input value={clientId} onChange={(event) => setClientId(event.target.value)} placeholder="例如 Ov23li..." />
                  <Button variant="outline" onClick={save} disabled={!clientId.trim() || saveClient.isPending}>
                    保存
                  </Button>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button onClick={start} disabled={startDevice.isPending || polling}>
                  {startDevice.isPending || polling ? <Loader2 className="h-4 w-4 animate-spin" /> : <Github className="h-4 w-4" />}
                  {polling ? "等待授权" : device ? "重新开始" : "连接 GitHub"}
                </Button>
                {polling && (
                  <Button variant="outline" onClick={stopWaiting}>
                    停止等待
                  </Button>
                )}
                <Button variant="outline" onClick={() => window.open("https://github.com/settings/developers", "_blank", "noopener,noreferrer")}>
                  <ExternalLink className="h-4 w-4" />
                  创建 OAuth App
                </Button>
              </div>
            </>
          )}

          {device && !auth?.connected && (
            <div className="rounded-xl border bg-muted/40 p-4">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <Badge variant="secondary">授权码</Badge>
                <code className="rounded-lg border bg-background px-3 py-2 text-lg font-semibold tracking-wider">{device.user_code}</code>
                <Button variant="ghost" size="icon" onClick={() => navigator.clipboard.writeText(device.user_code)}>
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" onClick={() => authUrl && window.open(authUrl, "_blank", "noopener,noreferrer")}>
                  <ExternalLink className="h-4 w-4" />
                  打开授权页面
                </Button>
                {polling && (
                  <Badge variant="outline">
                    <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                    等待授权
                  </Badge>
                )}
              </div>
            </div>
          )}

          {message && <div className="rounded-xl border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">{message}</div>}
        </div>
      </DialogContent>
    </Dialog>
  );
}
