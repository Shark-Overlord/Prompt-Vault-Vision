import { Badge } from "../ui/badge";
import { qualityLabels } from "../../lib/constants";

export function QualityBadge({ value }: { value?: string }) {
  const variant = value === "rejected" ? "destructive" : value === "excellent" || value === "good" ? "default" : "secondary";
  return <Badge variant={variant}>{qualityLabels[value || ""] || value || "未评级"}</Badge>;
}
