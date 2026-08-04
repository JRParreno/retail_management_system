"use client";

import { useMemo, useState } from "react";
import { Check, ChevronsUpDown } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export type ComboboxOption = {
  value: string;
  label: string;
  description?: string;
  keywords?: string;
};

type Props = {
  options: ComboboxOption[];
  value: string;
  onValueChange: (value: string) => void;
  placeholder?: string;
  searchPlaceholder?: string;
  emptyText?: string;
  className?: string;
  disabled?: boolean;
};

/** cmdk item key: label-first so UUIDs never become the visible/search token alone. */
function itemKey(opt: ComboboxOption): string {
  return `${opt.label}::${opt.value}`;
}

function findOption(
  options: ComboboxOption[],
  value: string,
): ComboboxOption | null {
  const needle = value.trim().toLowerCase();
  if (!needle) return null;
  return (
    options.find((o) => o.value.toLowerCase() === needle) ??
    options.find((o) => itemKey(o).toLowerCase() === needle) ??
    null
  );
}

export function SearchableCombobox({
  options,
  value,
  onValueChange,
  placeholder = "Search and select…",
  searchPlaceholder = "Type to search…",
  emptyText = "No results found.",
  className,
  disabled,
}: Props) {
  const [open, setOpen] = useState(false);

  const selected = useMemo(
    () => findOption(options, value),
    [options, value],
  );

  const displayLabel = selected?.label?.trim() || placeholder;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        disabled={disabled}
        render={(props) => (
          <Button
            {...props}
            type="button"
            variant="outline"
            role="combobox"
            aria-expanded={open}
            disabled={disabled}
            className={cn(
              props.className,
              "min-h-11 w-full justify-between px-3 font-normal",
              !selected && "text-muted-foreground",
              className,
            )}
          >
            <span className="truncate text-left">{displayLabel}</span>
            <ChevronsUpDown className="ml-2 size-4 shrink-0 opacity-50" />
          </Button>
        )}
      />
      <PopoverContent
        align="start"
        className="w-[var(--anchor-width)] min-w-[280px] p-0"
        sideOffset={4}
      >
        <Command
          filter={(itemValue, search, keywords) => {
            const haystack = [itemValue, ...(keywords ?? [])]
              .filter(Boolean)
              .join(" ")
              .toLowerCase();
            return haystack.includes(search.toLowerCase()) ? 1 : 0;
          }}
        >
          <CommandInput placeholder={searchPlaceholder} />
          <CommandList>
            <CommandEmpty>{emptyText}</CommandEmpty>
            <CommandGroup>
              {options.map((opt) => (
                <CommandItem
                  key={opt.value}
                  value={itemKey(opt)}
                  keywords={[
                    opt.label,
                    opt.description ?? "",
                    opt.keywords ?? "",
                    opt.value,
                  ]}
                  onSelect={() => {
                    onValueChange(opt.value);
                    setOpen(false);
                  }}
                  className="min-h-11 cursor-pointer"
                >
                  <Check
                    className={cn(
                      "mr-2 size-4 shrink-0",
                      value === opt.value ? "opacity-100" : "opacity-0",
                    )}
                  />
                  <span className="flex min-w-0 flex-col text-left">
                    <span className="truncate font-medium">{opt.label}</span>
                    {opt.description ? (
                      <span className="truncate text-xs text-muted-foreground">
                        {opt.description}
                      </span>
                    ) : null}
                  </span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
