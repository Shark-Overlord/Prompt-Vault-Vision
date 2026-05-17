import { FormEvent, Fragment, useMemo, useState } from "react";
import {
  Bot,
  CheckCircle2,
  KeyRound,
  Loader2,
  Pencil,
  Plus,
  RadioTower,
  Server,
  Settings2,
  ShieldCheck,
  Trash2,
  XCircle
} from "lucide-react";
import {
  useAiConfigModels,
  useAiConfigs,
  useCreateAiConfig,
  useDeleteAiConfig,
  useTestAiConfig,
  useUpdateAiConfig
} from "../hooks/useAiConfigs";
import type { AiConfig, AiConfigPayload, AiModelsResult, AiProvider } from "../lib/types";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Switch } from "../components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Textarea } from "../components/ui/textarea";

type AiForm = {
  name: string;
  provider: AiProvider;
  base_url: string;
  model: string;
  api_key: string;
  clear_api_key: boolean;
  is_default: boolean;
  enabled: boolean;
  temperature: string;
  timeout_seconds: string;
};

const providerDefaults: Record<AiProvider, Pick<AiForm, "name" | "base_url" | "model"> & { description: string }> = {
  deepseek: {
    name: "DeepSeek",
    base_url: "https://api.deepseek.com",
    model: "deepseek-chat",
    description: "云端 API，适合稳定做仓库总结、Prompt 中文解释和证据摘要。"
  },
  lm_studio: {
    name: "LM Studio 本地服务",
    base_url: "http://127.0.0.1:1234/v1",
    model: "local-model",
    description: "本地 OpenAI-compatible 服务，适合隐私数据和离线扫描。"
  }
};

const defaultForm: AiForm = {
  name: providerDefaults.deepseek.name,
  provider: "deepseek",
  base_url: providerDefaults.deepseek.base_url,
  model: providerDefaults.deepseek.model,
  api_key: "",
  clear_api_key: false,
  is_default: true,
  enabled: true,
  temperature: "0.2",
  timeout_seconds: "60"
};

function parseError(error: unknown) {
  if (!(error instanceof Error)) return "";
  try {
    const payload = JSON.parse(error.message) as { detail?: string };
    return payload.detail || error.message;
  } catch {
    return error.message;
  }
}

function formatDateTime(value?: string | null) {
  if (!value) return "未测试";
  const cleaned = value.replace(/([+-]\d{2}:\d{2}|Z)$/i, "");
  return cleaned.replace("T", " ");
}

function formFromConfig(config: AiConfig): AiForm {
  return {
    name: config.name,
    provider: config.provider,
    base_url: config.base_url,
    model: config.model,
    api_key: "",
    clear_api_key: false,
    is_default: config.is_default,
    enabled: config.enabled,
    temperature: String(config.temperature ?? 0.2),
    timeout_seconds: String(config.timeout_seconds ?? 60)
  };
}

function payloadFromForm(form: AiForm, mode: "create" | "edit"): AiConfigPayload {
  const payload: AiConfigPayload = {
    name: form.name.trim(),
    provider: form.provider,
    base_url: form.base_url.trim(),
    model: form.model.trim(),
    is_default: form.is_default,
    enabled: form.enabled,
    temperature: Number(form.temperature) || 0.2,
    timeout_seconds: Number(form.timeout_seconds) || 60
  };
  if (form.api_key.trim()) payload.api_key = form.api_key.trim();
  if (mode === "create" && !form.api_key.trim()) payload.api_key = "";
  if (mode === "edit" && form.clear_api_key) payload.clear_api_key = true;
  return payload;
}

function TestStatusBadge({ config }: { config: AiConfig }) {
  if (config.last_test_status === "success") {
    return (
      <Badge>
        <CheckCircle2 className="size-3" />
        连接成功
      </Badge>
    );
  }
  if (config.last_test_status === "failed") {
    return (
      <Badge variant="destructive">
        <XCircle className="size-3" />
        连接失败
      </Badge>
    );
  }
  return <Badge variant="outline">未测试</Badge>;
}

function AiConfigForm({
  form,
  setForm,
  mode,
  isPending,
  error,
  onSubmit,
  onCancel
}: {
  form: AiForm;
  setForm: (form: AiForm) => void;
  mode: "create" | "edit";
  isPending: boolean;
  error: unknown;
  onSubmit: (event: FormEvent) => void;
  onCancel: () => void;
}) {
  const providerDescription = providerDefaults[form.provider].description;

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <DialogHeader>
        <DialogTitle>{mode === "create" ? "新增 AI 配置" : "编辑 AI 配置"}</DialogTitle>
        <DialogDescription>
          密钥保存在本地 SQLite，只用于后端调用模型；列表和详情接口不会返回明文密钥。
        </DialogDescription>
      </DialogHeader>

      <div className="rounded-lg border bg-muted/20 p-3 text-sm text-muted-foreground">
        {providerDescription}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <label className="space-y-2">
          <span className="text-xs text-muted-foreground">提供商</span>
          <Select
            value={form.provider}
            onValueChange={(value) => {
              const provider = value as AiProvider;
              const preset = providerDefaults[provider];
              setForm({
                ...form,
                provider,
                name: mode === "create" ? preset.name : form.name,
                base_url: preset.base_url,
                model: preset.model,
                api_key: "",
                clear_api_key: false
              });
            }}
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="deepseek">DeepSeek</SelectItem>
              <SelectItem value="lm_studio">LM Studio</SelectItem>
            </SelectContent>
          </Select>
        </label>

        <label className="space-y-2">
          <span className="text-xs text-muted-foreground">配置名称</span>
          <Input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
        </label>

        <label className="space-y-2 md:col-span-2">
          <span className="text-xs text-muted-foreground">Base URL</span>
          <Input value={form.base_url} onChange={(event) => setForm({ ...form, base_url: event.target.value })} />
        </label>

        <label className="space-y-2">
          <span className="text-xs text-muted-foreground">模型名称</span>
          <Input value={form.model} onChange={(event) => setForm({ ...form, model: event.target.value })} />
        </label>

        <label className="space-y-2">
          <span className="text-xs text-muted-foreground">
            API Key {mode === "edit" ? "（留空则保留原密钥）" : form.provider === "lm_studio" ? "（可留空）" : ""}
          </span>
          <Input
            type="password"
            value={form.api_key}
            placeholder={mode === "edit" ? "不修改密钥" : "输入密钥"}
            onChange={(event) => setForm({ ...form, api_key: event.target.value, clear_api_key: false })}
          />
        </label>

        <label className="space-y-2">
          <span className="text-xs text-muted-foreground">温度</span>
          <Input value={form.temperature} onChange={(event) => setForm({ ...form, temperature: event.target.value })} />
        </label>

        <label className="space-y-2">
          <span className="text-xs text-muted-foreground">超时秒数</span>
          <Input value={form.timeout_seconds} onChange={(event) => setForm({ ...form, timeout_seconds: event.target.value })} />
        </label>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <label className="flex items-center justify-between rounded-lg border bg-muted/10 p-3">
          <span className="text-sm">启用</span>
          <Switch checked={form.enabled} onCheckedChange={(checked) => setForm({ ...form, enabled: checked })} />
        </label>
        <label className="flex items-center justify-between rounded-lg border bg-muted/10 p-3">
          <span className="text-sm">设为默认</span>
          <Switch checked={form.is_default} onCheckedChange={(checked) => setForm({ ...form, is_default: checked, enabled: checked ? true : form.enabled })} />
        </label>
        {mode === "edit" && (
          <label className="flex items-center justify-between rounded-lg border bg-muted/10 p-3">
            <span className="text-sm">清空密钥</span>
            <Switch checked={form.clear_api_key} onCheckedChange={(checked) => setForm({ ...form, clear_api_key: checked, api_key: checked ? "" : form.api_key })} />
          </label>
        )}
      </div>

      {Boolean(error) && <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">{parseError(error)}</div>}

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>
          取消
        </Button>
        <Button type="submit" disabled={isPending}>
          {isPending && <Loader2 className="size-4 animate-spin" />}
          保存配置
        </Button>
      </DialogFooter>
    </form>
  );
}

export function SystemConfigPage() {
  const { data: configs = [], isLoading } = useAiConfigs();
  const createConfig = useCreateAiConfig();
  const updateConfig = useUpdateAiConfig();
  const deleteConfig = useDeleteAiConfig();
  const testConfig = useTestAiConfig();
  const modelsRequest = useAiConfigModels();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingConfig, setEditingConfig] = useState<AiConfig | null>(null);
  const [form, setForm] = useState<AiForm>(defaultForm);
  const [lastTest, setLastTest] = useState<Record<number, string>>({});
  const [modelsResult, setModelsResult] = useState<Record<number, AiModelsResult>>({});

  const defaultConfig = useMemo(() => configs.find((config) => config.is_default), [configs]);

  const openCreate = () => {
    setEditingConfig(null);
    setForm({ ...defaultForm, is_default: configs.length === 0 });
    setDialogOpen(true);
  };

  const openEdit = (config: AiConfig) => {
    setEditingConfig(config);
    setForm(formFromConfig(config));
    setDialogOpen(true);
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (editingConfig) {
      updateConfig.mutate(
        { id: editingConfig.id, payload: payloadFromForm(form, "edit") },
        { onSuccess: () => setDialogOpen(false) }
      );
      return;
    }
    createConfig.mutate(payloadFromForm(form, "create"), { onSuccess: () => setDialogOpen(false) });
  };

  const handleTest = (config: AiConfig) => {
    testConfig.mutate(config.id, {
      onSuccess: (result) => {
        setLastTest((current) => ({ ...current, [config.id]: result.message }));
      },
      onError: (error) => {
        setLastTest((current) => ({ ...current, [config.id]: parseError(error) || "测试失败" }));
      }
    });
  };

  const handleModels = (config: AiConfig) => {
    modelsRequest.mutate(config.id, {
      onSuccess: (result) => setModelsResult((current) => ({ ...current, [config.id]: result })),
      onError: (error) =>
        setModelsResult((current) => ({
          ...current,
          [config.id]: { status: "failed", message: parseError(error) || "模型列表读取失败", models: [], latency_ms: 0 }
        }))
    });
  };

  return (
    <div className="space-y-5">
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="text-xs text-muted-foreground">AI Runtime</div>
            <CardTitle className="flex items-center gap-2">
              <Settings2 className="size-5" />
              系统配置
            </CardTitle>
            <CardDescription>
              配置 DeepSeek 或 LM Studio，后续仓库总结、Prompt 解释、证据链摘要都会从默认 AI 配置读取。
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-3">
            <div className="rounded-lg border bg-muted/10 p-4">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Bot className="size-4" />
                AI 配置数
              </div>
              <div className="mt-3 text-3xl font-semibold">{configs.length}</div>
            </div>
            <div className="rounded-lg border bg-muted/10 p-4">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <ShieldCheck className="size-4" />
                默认配置
              </div>
              <div className="mt-3 truncate text-lg font-medium">{defaultConfig?.name || "未设置"}</div>
            </div>
            <div className="rounded-lg border bg-muted/10 p-4">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <KeyRound className="size-4" />
                密钥策略
              </div>
              <div className="mt-3 text-sm leading-6 text-muted-foreground">保存在本地 SQLite；接口不回传明文。</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>后续工作流</CardTitle>
            <CardDescription>第一步先打通配置和连接测试。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="size-4 text-foreground" />
              AI 配置入 SQLite
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="size-4 text-foreground" />
              支持 DeepSeek / LM Studio
            </div>
            <div className="flex items-center gap-2">
              <RadioTower className="size-4" />
              连接测试使用 Chat Completions
            </div>
            <div className="flex items-center gap-2">
              <Server className="size-4" />
              LangGraph 扫描总结流稍后接入
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="border-b">
          <div>
            <div className="text-xs text-muted-foreground">Provider Settings</div>
            <CardTitle>AI 配置列表</CardTitle>
          </div>
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button onClick={openCreate}>
                <Plus className="size-4" />
                新增配置
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <AiConfigForm
                form={form}
                setForm={setForm}
                mode={editingConfig ? "edit" : "create"}
                isPending={createConfig.isPending || updateConfig.isPending}
                error={createConfig.error || updateConfig.error}
                onSubmit={handleSubmit}
                onCancel={() => setDialogOpen(false)}
              />
            </DialogContent>
          </Dialog>
        </CardHeader>

        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>配置</TableHead>
                <TableHead>连接</TableHead>
                <TableHead>模型</TableHead>
                <TableHead>密钥</TableHead>
                <TableHead>最近测试</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={6} className="py-10 text-center text-muted-foreground">
                    <Loader2 className="mx-auto mb-2 size-5 animate-spin" />
                    正在读取 AI 配置
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && configs.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="py-12 text-center">
                    <div className="font-medium">还没有 AI 配置</div>
                    <div className="mt-2 text-sm text-muted-foreground">新增 DeepSeek 或 LM Studio 配置后，可以立即测试连接。</div>
                  </TableCell>
                </TableRow>
              )}
              {configs.map((config) => {
                const testing = testConfig.isPending && testConfig.variables === config.id;
                const loadingModels = modelsRequest.isPending && modelsRequest.variables === config.id;
                const modelResult = modelsResult[config.id];
                return (
                  <Fragment key={config.id}>
                    <TableRow>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <div className="flex size-9 items-center justify-center rounded-lg border bg-muted/30">
                            {config.provider === "deepseek" ? <Bot className="size-4" /> : <Server className="size-4" />}
                          </div>
                          <div>
                            <div className="flex items-center gap-2 font-medium">
                              {config.name}
                              {config.is_default && <Badge variant="secondary">默认</Badge>}
                              {!config.enabled && <Badge variant="outline">已停用</Badge>}
                            </div>
                            <div className="mt-1 text-xs text-muted-foreground">{config.provider_label || config.provider}</div>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="max-w-[260px] truncate text-sm">{config.base_url}</div>
                        <div className="mt-1 text-xs text-muted-foreground">超时 {config.timeout_seconds}s</div>
                      </TableCell>
                      <TableCell>
                        <div className="text-sm">{config.model}</div>
                        <div className="mt-1 text-xs text-muted-foreground">temperature {config.temperature}</div>
                      </TableCell>
                      <TableCell>
                        {config.api_key_set ? <Badge>已保存</Badge> : <Badge variant="outline">未设置</Badge>}
                      </TableCell>
                      <TableCell>
                        <TestStatusBadge config={config} />
                        <div className="mt-1 text-xs text-muted-foreground">{formatDateTime(config.last_test_at)}</div>
                      </TableCell>
                      <TableCell>
                        <div className="flex justify-end gap-2">
                          <Button variant="outline" size="sm" onClick={() => handleTest(config)} disabled={testing}>
                            {testing ? <Loader2 className="size-4 animate-spin" /> : <RadioTower className="size-4" />}
                            测试
                          </Button>
                          <Button variant="outline" size="sm" onClick={() => handleModels(config)} disabled={loadingModels}>
                            {loadingModels ? <Loader2 className="size-4 animate-spin" /> : <Server className="size-4" />}
                            模型
                          </Button>
                          <Button variant="ghost" size="icon" onClick={() => openEdit(config)}>
                            <Pencil className="size-4" />
                          </Button>
                          <Button variant="destructive" size="icon" onClick={() => deleteConfig.mutate(config.id)} disabled={deleteConfig.isPending}>
                            <Trash2 className="size-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                    {(lastTest[config.id] || modelResult) && (
                      <TableRow>
                        <TableCell colSpan={6} className="bg-muted/10">
                          <div className="grid gap-3 text-sm md:grid-cols-2">
                            {lastTest[config.id] && <Textarea value={lastTest[config.id]} readOnly className="min-h-20 resize-none" />}
                            {modelResult && (
                              <Textarea
                                value={`${modelResult.message}${modelResult.models.length ? `\n\n${modelResult.models.join("\n")}` : ""}`}
                                readOnly
                                className="min-h-20 resize-none"
                              />
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
