import type { SelectHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  options: string[];
}

export function Select({ options, className, ...props }: SelectProps) {
  return (
    <select
      className={cn(
        "h-10 rounded-md border border-border bg-white px-3 text-sm text-foreground shadow-sm outline-none focus:border-primary",
        className,
      )}
      {...props}
    >
      {options.map((option) => (
        <option key={option} value={option}>
          {option}
        </option>
      ))}
    </select>
  );
}
