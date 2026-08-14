"use client";

import { useId } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { presetRange } from "@/lib/dates";

export function DateRangeFilter({
  start,
  end,
  onStartChange,
  onEndChange,
  onApply,
  disabled,
}: {
  start: string;
  end: string;
  onStartChange: (value: string) => void;
  onEndChange: (value: string) => void;
  onApply: (start: string, end: string) => void;
  disabled?: boolean;
}) {
  const id = useId();

  function applyPreset(days: number) {
    const next = presetRange(days);
    onStartChange(next.start);
    onEndChange(next.end);
    onApply(next.start, next.end);
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="secondary"
          className="min-h-11"
          disabled={disabled}
          onClick={() => applyPreset(1)}
        >
          Today
        </Button>
        <Button
          type="button"
          variant="secondary"
          className="min-h-11"
          disabled={disabled}
          onClick={() => applyPreset(7)}
        >
          Week
        </Button>
        <Button
          type="button"
          variant="secondary"
          className="min-h-11"
          disabled={disabled}
          onClick={() => applyPreset(30)}
        >
          Month
        </Button>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
        <div className="space-y-2">
          <Label htmlFor={`${id}-start`}>Start</Label>
          <Input
            id={`${id}-start`}
            type="date"
            className="min-h-11"
            value={start}
            disabled={disabled}
            onChange={(e) => onStartChange(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor={`${id}-end`}>End</Label>
          <Input
            id={`${id}-end`}
            type="date"
            className="min-h-11"
            value={end}
            disabled={disabled}
            onChange={(e) => onEndChange(e.target.value)}
          />
        </div>
        <Button
          type="button"
          className="min-h-11"
          disabled={disabled}
          onClick={() => onApply(start, end)}
        >
          Apply
        </Button>
      </div>
    </div>
  );
}
