import { motion } from "framer-motion";
import { Copy, ExternalLink, ImageOff, Star } from "lucide-react";
import type { PromptPair } from "../../lib/types";
import { assetUrl, truncate } from "../../lib/utils";
import { categoryLabels, visualAssetTypeLabels } from "../../lib/constants";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { QualityBadge } from "./QualityBadge";
import { StatusBadge } from "./StatusBadge";

export function PromptCard({ pair, onOpen, onQuickStatus }: { pair: PromptPair; onOpen: (pair: PromptPair) => void; onQuickStatus: (id: number, status: string) => void }) {
  const image = assetUrl(pair.image_local_path);
  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -4 }}
      className="group relative overflow-hidden rounded-xl border bg-card text-card-foreground shadow-sm"
    >
      <button className="block w-full text-left" onClick={() => onOpen(pair)}>
        <div className="min-h-56 bg-muted">
          {image ? (
            <img src={image} alt={pair.repo_name} className="h-full max-h-[420px] min-h-56 w-full object-cover" loading="lazy" />
          ) : (
            <div className="grid h-64 place-items-center text-muted-foreground">
              <ImageOff className="h-10 w-10" />
            </div>
          )}
        </div>
        <div className="space-y-3 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge>{categoryLabels[pair.category] || pair.category}</Badge>
            <Badge variant="secondary">{pair.scenario || "other"}</Badge>
            {pair.visual_asset_type && pair.visual_asset_type !== "uncategorized" && (
              <Badge variant="outline">{visualAssetTypeLabels[pair.visual_asset_type] || pair.visual_asset_type}</Badge>
            )}
            <QualityBadge value={pair.quality_level} />
            <StatusBadge value={pair.selection_status} />
          </div>
          <div className="text-sm font-medium">{pair.repo_name || "未命名 Prompt"}</div>
          <p className="text-xs leading-5 text-muted-foreground">{truncate(pair.prompt_cn_explanation || pair.original_prompt, 128)}</p>
        </div>
      </button>
      <div className="flex items-center justify-between border-t px-4 py-2">
        <div className="text-xs text-muted-foreground">{truncate(pair.original_prompt, 42)}</div>
        <div className="flex gap-1">
          <Button size="icon" variant="ghost" onClick={() => navigator.clipboard.writeText(pair.original_prompt || "")}>
            <Copy className="h-4 w-4" />
          </Button>
          <Button size="icon" variant="ghost" onClick={() => onQuickStatus(pair.id, "featured")}>
            <Star className="h-4 w-4" />
          </Button>
          <Button size="icon" variant="ghost" onClick={() => window.open(pair.source_page_url || pair.repo_url, "_blank")}>
            <ExternalLink className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </motion.article>
  );
}
