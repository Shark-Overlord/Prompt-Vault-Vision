import { ExportPanel } from "../components/export/ExportPanel";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";

export function ExportPage() {
  return (
    <div className="grid gap-5 xl:grid-cols-[1.15fr_0.85fr]">
      <ExportPanel />
      <Card>
        <CardHeader>
          <div className="text-xs text-muted-foreground">Export Formats</div>
          <CardTitle>导出用途</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm leading-6 text-muted-foreground">
          <p>Markdown 用于人工阅读和商品库文案整理。</p>
          <p>JSON 用于网站工具或二次程序处理。</p>
          <p>桌面 AI Skill 数据用于沉淀精选 Prompt 能力包。</p>
          <p>CSV 用于表格审查、批量标注或外部运营流程。</p>
        </CardContent>
      </Card>
    </div>
  );
}
