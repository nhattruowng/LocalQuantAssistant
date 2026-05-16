import type { InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-10 rounded-md border border-border bg-white px-3 text-sm text-foreground shadow-sm outline-none focus:border-primary",
        className,
      )}
      {...props}
    />
  );
}
