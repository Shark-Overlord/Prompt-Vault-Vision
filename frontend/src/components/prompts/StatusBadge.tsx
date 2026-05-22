import { Badge } from "../ui/badge";
import { repoStatusLabels, statusLabels } from "../../lib/constants";

export function StatusBadge({ value }: { value?: string }) {
  const variant = value === "rejected" ? "destructive" : value === "featured" || value === "ready_to_scan" ? "default" : value === "normal" ? "secondary" : "outline";
  return <Badge variant={variant}>{repoStatusLabels[value || ""] || statusLabels[value || ""] || value || "未设置"}</Badge>;
}
