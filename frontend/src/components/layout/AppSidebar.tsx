import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { ChevronDown, Sparkles } from "lucide-react";
import { navGroups } from "../../lib/constants";
import { cn } from "../../lib/utils";
import { Card } from "../ui/card";

const SIDEBAR_GROUP_STORAGE_KEY = "visual_prompt_sidebar_groups";

function defaultExpandedGroups() {
  return Object.fromEntries(navGroups.map((group) => [group.label, true]));
}

export function AppSidebar() {
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>(() => {
    const defaults = defaultExpandedGroups();
    if (typeof window === "undefined") return defaults;
    try {
      const saved = window.localStorage.getItem(SIDEBAR_GROUP_STORAGE_KEY);
      return saved ? { ...defaults, ...JSON.parse(saved) } : defaults;
    } catch {
      return defaults;
    }
  });

  useEffect(() => {
    window.localStorage.setItem(SIDEBAR_GROUP_STORAGE_KEY, JSON.stringify(expandedGroups));
  }, [expandedGroups]);

  const toggleGroup = (label: string) => {
    setExpandedGroups((current) => ({ ...current, [label]: !current[label] }));
  };

  return (
    <Card className="fixed left-4 top-4 z-30 flex h-[calc(100vh-2rem)] w-64 flex-col p-4">
      <div className="mb-6 flex items-center gap-3">
        <div className="grid h-10 w-10 place-items-center rounded-lg border bg-muted">
          <Sparkles className="h-5 w-5" />
        </div>
        <div>
          <div className="text-sm font-semibold">Visual Prompt</div>
          <div className="text-xs text-muted-foreground">本地视觉资产库</div>
        </div>
      </div>
      <nav className="sidebar-scroll min-h-0 flex-1 space-y-3 overflow-y-auto pr-1" aria-label="主导航">
        {navGroups.map((group) => (
          <div key={group.label} className="space-y-1.5">
            <button
              type="button"
              className="flex h-7 w-full items-center justify-between rounded-md px-3 text-[11px] font-medium uppercase tracking-wide text-muted-foreground/70 transition hover:bg-muted/40 hover:text-muted-foreground"
              aria-expanded={Boolean(expandedGroups[group.label])}
              onClick={() => toggleGroup(group.label)}
            >
              <span>{group.label}</span>
              <ChevronDown
                className={cn(
                  "h-3.5 w-3.5 transition-transform duration-200",
                  !expandedGroups[group.label] && "-rotate-90"
                )}
              />
            </button>
            {expandedGroups[group.label] && (
              <div className="space-y-1">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={`${item.href}-${item.label}`}
                      to={item.href}
                      end={item.href === "/"}
                      className={({ isActive }) =>
                        cn(
                          "flex h-10 items-center gap-3 rounded-lg px-3 text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground",
                          isActive && "bg-muted text-foreground"
                        )
                      }
                    >
                      <Icon className="h-4 w-4 shrink-0" />
                      <span className="truncate">{item.label}</span>
                    </NavLink>
                  );
                })}
              </div>
            )}
          </div>
        ))}
      </nav>
      <div className="mt-auto rounded-xl border bg-muted/40 p-3">
        <div className="text-xs text-muted-foreground">SQLite 主索引</div>
        <div className="mt-1 text-sm">data/visual_prompt_library.db</div>
      </div>
    </Card>
  );
}
