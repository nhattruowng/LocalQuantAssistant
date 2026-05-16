import type { ReactNode } from "react";

interface DataTableProps<T extends object> {
  rows: T[];
  columns: { key: keyof T; label: string; render?: (value: T[keyof T], row: T) => ReactNode }[];
  emptyText: string;
}

export function DataTable<T extends object>({ rows, columns, emptyText }: DataTableProps<T>) {
  if (!rows.length) {
    return <div className="rounded-lg border border-dashed border-border p-6 text-muted-foreground">{emptyText}</div>;
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-white">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-border text-sm">
          <thead className="bg-muted">
            <tr>
              {columns.map((column) => (
                <th key={String(column.key)} className="px-4 py-3 text-left font-medium text-muted-foreground">
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((row, index) => (
              <tr key={index} className="hover:bg-muted/40">
                {columns.map((column) => (
                  <td key={String(column.key)} className="whitespace-nowrap px-4 py-3">
                    {column.render ? column.render(row[column.key], row) : String(row[column.key] ?? "-")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
