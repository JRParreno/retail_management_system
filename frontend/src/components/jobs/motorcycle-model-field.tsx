"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { clientApi, toastError } from "@/lib/client-api";
import type { MotorcycleModel } from "@/lib/types";
import { cn } from "@/lib/utils";

type Props = {
  id?: string;
  label?: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
};

export function MotorcycleModelField({
  id = "motorcycle_model",
  label = "Motorcycle model",
  value,
  onChange,
  required,
}: Props) {
  const [models, setModels] = useState<MotorcycleModel[]>([]);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    clientApi<MotorcycleModel[]>("/motorcycle-models")
      .then(setModels)
      .catch(toastError);
  }, []);

  useEffect(() => {
    function onPointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, []);

  const suggestions = useMemo(() => {
    const term = value.trim().toLowerCase();
    const rows = !term
      ? models
      : models.filter((m) => {
          const haystack = `${m.brand} ${m.name} ${m.display_name}`.toLowerCase();
          return haystack.includes(term);
        });
    return rows.slice(0, 12);
  }, [models, value]);

  const exactMatch = useMemo(() => {
    const term = value.trim().toLowerCase();
    if (!term) return false;
    return models.some((m) => m.display_name.toLowerCase() === term);
  }, [models, value]);

  return (
    <div ref={rootRef} className="relative space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        className="min-h-11"
        required={required}
        autoComplete="off"
        placeholder="Type or pick — e.g. Honda Click 125i"
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "Escape") setOpen(false);
        }}
      />
      {open && suggestions.length > 0 ? (
        <ul
          className={cn(
            "absolute z-50 mt-1 max-h-60 w-full overflow-auto rounded-lg border bg-popover p-1 shadow-md",
          )}
          role="listbox"
        >
          {suggestions.map((m) => {
            const selected =
              value.trim().toLowerCase() === m.display_name.toLowerCase();
            return (
              <li key={m.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={selected}
                  className={cn(
                    "flex min-h-11 w-full flex-col items-start rounded-md px-3 py-2 text-left text-sm hover:bg-accent",
                    selected && "bg-accent",
                  )}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => {
                    onChange(m.display_name);
                    setOpen(false);
                  }}
                >
                  <span className="font-medium">{m.display_name}</span>
                  <span className="text-xs text-muted-foreground">{m.brand}</span>
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
      <p className="text-xs text-muted-foreground">
        {value.trim()
          ? exactMatch
            ? "Matched a catalog model"
            : "Custom free-text model"
          : "Free text allowed — suggestions appear as you type"}
      </p>
    </div>
  );
}
