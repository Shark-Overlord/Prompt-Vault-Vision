import type { ReactNode } from "react";
import { categoryLabels, qualityLabels, statusLabels } from "../../lib/constants";
import { useFilterStore } from "../../stores/useFilterStore";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";

function FilterSelect({
  value,
  placeholder,
  options,
  onChange
}: {
  value: string;
  placeholder: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <Select value={value || "__all"} onValueChange={(next) => onChange(next === "__all" ? "" : next)}>
      <SelectTrigger className="min-w-40">
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="__all">{placeholder}</SelectItem>
        {options.map((item) => (
          <SelectItem key={item.value} value={item.value}>
            {item.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

type FilterBarProps = {
  showSelection?: boolean;
  showCategory?: boolean;
  leading?: ReactNode;
  trailing?: ReactNode;
  onReset?: () => void;
};

export function FilterBar({ showSelection = true, showCategory = true, leading, trailing, onReset }: FilterBarProps) {
  const { category, qualityLevel, selectionStatus, setCategory, setQualityLevel, setSelectionStatus, reset } = useFilterStore();
  const handleReset = () => {
    reset();
    onReset?.();
  };

  return (
    <Card className="mb-5 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
        {leading && <div className="min-w-0 flex-1">{leading}</div>}
        <div className="flex flex-wrap items-center gap-3">
          {showCategory && (
            <FilterSelect
              value={category}
              placeholder="全部分类"
              options={Object.entries(categoryLabels).map(([value, label]) => ({ value, label }))}
              onChange={setCategory}
            />
          )}
          <FilterSelect
            value={qualityLevel}
            placeholder="全部等级"
            options={Object.entries(qualityLabels).map(([value, label]) => ({ value, label }))}
            onChange={setQualityLevel}
          />
          {showSelection && (
            <FilterSelect
              value={selectionStatus}
              placeholder="全部结论"
              options={Object.entries(statusLabels).map(([value, label]) => ({ value, label }))}
              onChange={setSelectionStatus}
            />
          )}
          <Button variant="ghost" onClick={handleReset}>
            重置筛选
          </Button>
        </div>
        {trailing && <div className="shrink-0">{trailing}</div>}
      </div>
    </Card>
  );
}
