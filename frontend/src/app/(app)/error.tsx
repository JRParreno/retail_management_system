"use client";

import { useEffect } from "react";

import { buttonVariants } from "@/components/ui/button";
import { log } from "@/lib/logger";
import { cn } from "@/lib/utils";

export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    log.error("Unhandled UI error", {
      message: error.message,
      digest: error.digest,
      stack: error.stack,
    });
  }, [error]);

  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 px-4 text-center">
      <div className="space-y-2">
        <h1 className="text-xl font-semibold">Something went wrong</h1>
        <p className="max-w-md text-sm text-muted-foreground">
          An unexpected error occurred. If this keeps happening, tell support the
          reference below.
        </p>
        {error.digest ? (
          <p className="font-mono text-xs text-muted-foreground">
            ref: {error.digest}
          </p>
        ) : null}
      </div>
      <button
        type="button"
        className={cn(buttonVariants(), "min-h-11")}
        onClick={() => reset()}
      >
        Try again
      </button>
    </div>
  );
}
