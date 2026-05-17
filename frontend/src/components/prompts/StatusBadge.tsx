import { Badge } from "../ui/badge";
import { statusLabels } from "../../lib/constants";

export function StatusBadge({ value }: { value?: string }) {
  const variant = value === "rejected" ? "destructive" : value === "featured" ? "default" : value === "normal" ? "secondary" : "outline";
  return <Badge variant={variant}>{statusLabels[value || ""] || value || "未设置"}</Badge>;
}
