import { useEffect, useId, useMemo, useRef, useState } from "react";
import { cx } from "../lib/cx";
import { inputClass } from "./TextField";

export interface SelectItem {
  value: string;
  label: string;
}

interface SearchSelectProps {
  label: string;
  items: SelectItem[];
  value: string | null;
  onChange: (value: string | null) => void;
  placeholder?: string;
  error?: string;
  hint?: string;
  loading?: boolean;
  disabled?: boolean;
  emptyText?: string;
}

const normalize = (text: string) =>
  text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();

/** Combobox accesible (patrón ARIA 1.2) con búsqueda sin tildes. */
export function SearchSelect({
  label,
  items,
  value,
  onChange,
  placeholder,
  error,
  hint,
  loading,
  disabled,
  emptyText = "Sin resultados",
}: SearchSelectProps) {
  const id = useId();
  const listId = `${id}-list`;
  const selected = items.find((i) => i.value === value) ?? null;
  const [query, setQuery] = useState(selected?.label ?? "");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) setQuery(selected?.label ?? "");
  }, [selected, open]);

  const filtered = useMemo(() => {
    const q = normalize(query.trim());
    if (!q || (selected && query === selected.label)) return items;
    return items.filter((i) => normalize(i.label).includes(q));
  }, [items, query, selected]);

  const choose = (item: SelectItem) => {
    onChange(item.value);
    setQuery(item.label);
    setOpen(false);
  };

  const describedBy = [hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(" ") || undefined;

  return (
    <div
      ref={containerRef}
      className="relative flex flex-col gap-1.5"
      onBlur={(e) => {
        if (!containerRef.current?.contains(e.relatedTarget as Node | null)) setOpen(false);
      }}
    >
      <label htmlFor={id} className="font-bold">
        {label}
      </label>
      <input
        id={id}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={open && filtered[active] ? `${id}-opt-${active}` : undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        autoComplete="off"
        disabled={disabled || loading}
        placeholder={loading ? "Cargando programas…" : placeholder}
        value={query}
        className={inputClass(Boolean(error))}
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          setActive(0);
          if (selected) onChange(null);
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setOpen(true);
            setActive((a) => Math.min(a + 1, filtered.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((a) => Math.max(a - 1, 0));
          } else if (e.key === "Enter" && open && filtered[active]) {
            e.preventDefault();
            choose(filtered[active]);
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
      />
      {open && !loading && (
        <ul
          id={listId}
          role="listbox"
          aria-label={label}
          className="absolute top-full z-20 mt-1 max-h-64 w-full overflow-auto rounded-[var(--radius-control)] border-2 border-line bg-surface py-1 shadow-raised"
        >
          {filtered.length === 0 && <li className="px-4 py-3 text-muted">{emptyText}</li>}
          {filtered.map((item, index) => (
            <li
              key={item.value}
              id={`${id}-opt-${index}`}
              role="option"
              aria-selected={item.value === value}
              tabIndex={-1}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => choose(item)}
              onMouseEnter={() => setActive(index)}
              className={cx(
                "cursor-pointer px-4 py-3 min-h-11",
                index === active && "bg-surface-2",
                item.value === value && "font-bold text-primary-text",
              )}
            >
              {item.label}
            </li>
          ))}
        </ul>
      )}
      {hint && (
        <p id={`${id}-hint`} className="text-sm text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="text-sm font-bold text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
