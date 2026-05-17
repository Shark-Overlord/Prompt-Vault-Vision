import { Check, Clock, Star, X } from "lucide-react";
import { Button } from "../ui/button";

const options = [
  { value: "featured", label: "精选", icon: Star },
  { value: "normal", label: "普通", icon: Check },
  { value: "reference", label: "参考", icon: Clock },
  { value: "rejected", label: "拒绝", icon: X },
  { value: "pending_review", label: "待复查", icon: Clock }
];

export function SelectionStatusSwitch({ value, onChange }: { value?: string; onChange: (value: string) => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((item) => {
        const Icon = item.icon;
        const active = value === item.value;
        return (
          <Button key={item.value} type="button" variant={active ? "default" : "outline"} size="sm" onClick={() => onChange(item.value)}>
            <Icon className="h-3.5 w-3.5" />
            {item.label}
          </Button>
        );
      })}
    </div>
  );
}
