interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: SelectOption[];
  error?: string;
}

export function Select({ label, options, error, className = '', ...props }: SelectProps) {
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label className="text-xs font-semibold uppercase tracking-wider text-white/40">
          {label}
        </label>
      )}
      <select
        {...props}
        className={[
          'w-full rounded-sm px-3 py-2 text-sm font-mono text-white/80',
          'bg-white/[0.04] border focus:outline-none transition-colors cursor-pointer',
          error
            ? 'border-loss/50 focus:border-loss'
            : 'border-white/10 focus:border-white/25',
          className,
        ].join(' ')}
        style={{ background: '#131318' }}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value} style={{ background: '#131318' }}>
            {o.label}
          </option>
        ))}
      </select>
      {error && <span className="text-xs text-loss">{error}</span>}
    </div>
  );
}
