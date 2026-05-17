import { useState } from "react";
import { Plus, X } from "lucide-react";
import type { Tag } from "../../lib/types";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Input } from "../ui/input";

export function TagSelector({ tags = [], onChange }: { tags?: Tag[]; onChange: (tags: string[]) => void }) {
  const [draft, setDraft] = useState("");
  const names = tags.map((tag) => tag.name);
  const add = () => {
    const next = draft.trim();
    if (!next || names.includes(next)) return;
    onChange([...names, next]);
    setDraft("");
  };
  const remove = (name: string) => onChange(names.filter((item) => item !== name));

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {names.map((name) => (
          <Badge key={name} variant="secondary" className="gap-1">
            {name}
            <button onClick={() => remove(name)} className="text-muted-foreground hover:text-foreground">
              <X className="h-3 w-3" />
            </button>
          </Badge>
        ))}
      </div>
      <div className="flex gap-2">
        <Input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="添加标签" onKeyDown={(event) => event.key === "Enter" && add()} />
        <Button type="button" variant="outline" onClick={add}>
          <Plus className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
