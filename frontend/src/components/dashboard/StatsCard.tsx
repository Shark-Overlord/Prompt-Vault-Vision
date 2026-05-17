import type { LucideIcon } from "lucide-react";
import { motion } from "framer-motion";
import { Card, CardContent } from "../ui/card";

export function StatsCard({ title, value, icon: Icon, hint }: { title: string; value: number | string; icon: LucideIcon; accent?: "cyan" | "emerald" | "amber"; hint?: string }) {
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
      <Card>
        <CardContent className="flex items-start justify-between p-5">
          <div>
            <div className="text-xs text-muted-foreground">{title}</div>
            <div className="mt-3 text-3xl font-semibold">{value}</div>
            {hint && <div className="mt-2 text-xs text-muted-foreground">{hint}</div>}
          </div>
          <div className="grid h-10 w-10 place-items-center rounded-lg border bg-muted">
            <Icon className="h-5 w-5" />
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
