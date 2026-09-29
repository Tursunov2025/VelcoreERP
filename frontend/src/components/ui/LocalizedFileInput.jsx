import { useId, useState } from "react";
import { useLocale } from "../../context/LocaleContext";

export default function LocalizedFileInput({ className = "", onChange, disabled, ...props }) {
  const { t } = useLocale();
  const id = useId();
  const [name, setName] = useState("");

  return (
    <div className={`flex flex-wrap items-center gap-3 ${className}`}>
      <input
        {...props}
        id={id}
        type="file"
        disabled={disabled}
        className="sr-only"
        onChange={(event) => {
          setName(event.target.files?.[0]?.name || "");
          onChange?.(event);
        }}
      />
      <label
        htmlFor={id}
        aria-disabled={disabled || undefined}
        className="brand-btn-secondary cursor-pointer rounded-xl px-4 py-2 text-sm font-semibold aria-disabled:pointer-events-none aria-disabled:opacity-50"
      >
        {t("legacySettings.chooseFile")}
      </label>
      <span className="text-sm text-[var(--brand-muted)]">
        {name || t("legacySettings.noFileSelected")}
      </span>
    </div>
  );
}
