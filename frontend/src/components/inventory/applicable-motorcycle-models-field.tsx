"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { clientApi, toastError } from "@/lib/client-api";
import type { MotorcycleModel } from "@/lib/types";
import { cn } from "@/lib/utils";

type SelectedModel = {
  id: string;
  display_name: string;
  brand: string;
};

type Props = {
  selectedIds: string[];
  onChange: (ids: string[]) => void;
  /** Prefill labels when editing before catalog finishes loading */
  initialModels?: SelectedModel[];
};

export function ApplicableMotorcycleModelsField({
  selectedIds,
  onChange,
  initialModels = [],
}: Props) {
  const [models, setModels] = useState<MotorcycleModel[]>([]);
  const [query, setQuery] = useState("");
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

  const selectedById = useMemo(() => {
    const map = new Map<string, SelectedModel>();
    for (const m of initialModels) map.set(m.id, m);
    for (const m of models) {
      map.set(m.id, {
        id: m.id,
        display_name: m.display_name,
        brand: m.brand,
      });
    }
    return map;
  }, [initialModels, models]);

  const selected = useMemo(
    () =>
      selectedIds
        .map((id) => selectedById.get(id))
        .filter((m): m is SelectedModel => m != null),
    [selectedById, selectedIds],
  );

  const suggestions = useMemo(() => {
    const term = query.trim().toLowerCase();
    const selectedSet = new Set(selectedIds);
    const rows = models.filter((m) => {
      if (selectedSet.has(m.id)) return false;
      if (!term) return true;
      const haystack = `${m.brand} ${m.name} ${m.display_name}`.toLowerCase();
      return haystack.includes(term);
    });
    return rows.slice(0, 12);
  }, [models, query, selectedIds]);

  function addModel(model: MotorcycleModel) {
    if (selectedIds.includes(model.id)) return;
    onChange([...selectedIds, model.id]);
    setQuery("");
    setOpen(false);
  }

  function removeModel(id: string) {
    onChange(selectedIds.filter((x) => x !== id));
  }

  return (
    <div ref={rootRef} className="space-y-2">
      <Label htmlFor="applicable-models">Fits motorcycle models</Label>
      {selected.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {selected.map((m) => (
            <Badge key={m.id} variant="secondary" className="gap-1 pr-1">
              <span>{m.display_name}</span>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-6"
                onClick={() => removeModel(m.id)}
                aria-label={`Remove ${m.display_name}`}
              >
                <X className="size-3.5" />
              </Button>
            </Badge>
          ))}
        </div>
      ) : null}
      <Input
        id="applicable-models"
        className="min-h-11"
        autoComplete="off"
        placeholder="Search and add models — e.g. Honda Click 125i"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
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
            "max-h-60 w-full overflow-auto rounded-lg border bg-popover p-1 shadow-md",
          )}
          role="listbox"
        >
          {suggestions.map((m) => (
            <li key={m.id}>
              <button
                type="button"
                role="option"
                className="flex min-h-11 w-full flex-col items-start rounded-md px-3 py-2 text-left text-sm hover:bg-accent"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => addModel(m)}
              >
                <span className="font-medium">{m.display_name}</span>
                <span className="text-xs text-muted-foreground">{m.brand}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <p className="text-xs text-muted-foreground">
        Optional. Leave empty if the part fits many or unknown models. Pick from
        the catalog list used on jobs.
      </p>
    </div>
  );
}
