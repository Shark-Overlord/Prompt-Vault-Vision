import { useState } from "react";
import { Download, FileJson, FileText, Table2, WandSparkles } from "lucide-react";
import { api } from "../../lib/api";
import { Button } from "../ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";

const presets = [
  { format: "markdown", label: "Markdown 精选库", icon: FileText },
  { format: "json", label: "JSON 结构化数据", icon: FileJson },
  { format: "skill", label: "桌面 AI Skill 数据", icon: WandSparkles },
  { format: "csv", label: "CSV 表格", icon: Table2 }
];

const statuses = [
  { label: "精选 featured", value: "featured" },
  { label: "普通 normal", value: "normal" },
  { label: "仅参考 reference", value: "reference" },
  { label: "待复查 pending_review", value: "pending_review" }
];

export function ExportPanel() {
  const [format, setFormat] = useState("markdown");
  const [status, setStatus] = useState("featured");
  const [result, setResult] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const run = async () => {
    setLoading(true);
    try {
      const response = await api.exportData({ format, selection_status: status });
      setResult(response.path);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardDescription>ExportPanel</CardDescription>
        <CardTitle>导出 Prompt 资产</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 md:grid-cols-2">
          {presets.map((preset) => {
            const Icon = preset.icon;
            const active = preset.format === format;
            return (
              <button
                key={preset.format}
                onClick={() => setFormat(preset.format)}
                className={`rounded-xl border p-4 text-left transition ${active ? "border-primary bg-primary/10" : "border-border bg-card hover:bg-muted/40"}`}
              >
                <Icon className="mb-4 h-5 w-5 text-primary" />
                <div className="text-sm font-medium text-foreground">{preset.label}</div>
                <div className="mt-1 text-xs text-muted-foreground">按当前筛选结论生成本地文件</div>
              </button>
            );
          })}
        </div>
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger className="min-w-56">
              <SelectValue placeholder="选择导出范围" />
            </SelectTrigger>
            <SelectContent>
              {statuses.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button onClick={run} disabled={loading}>
            <Download className="h-4 w-4" />
            {loading ? "导出中" : "开始导出"}
          </Button>
        </div>
        {result && <div className="mt-4 rounded-xl border bg-muted/40 p-3 text-sm text-muted-foreground">已生成：{result}</div>}
      </CardContent>
    </Card>
  );
}
