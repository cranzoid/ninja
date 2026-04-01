interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export function Input({ label, error, className = '', ...props }: InputProps) {
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label className="text-xs font-semibold uppercase tracking-wider text-white/40">
          {label}
        </label>
      )}
      <input
        {...props}
        className={[
          'w-full rounded-sm px-3 py-2 text-sm font-mono text-white/80',
          'bg-white/[0.04] border focus:outline-none transition-colors',
          error
            ? 'border-loss/50 focus:border-loss'
            : 'border-white/10 focus:border-white/25',
          'placeholder:text-white/25',
          className,
        ].join(' ')}
      />
      {error && <span className="text-xs text-loss">{error}</span>}
    </div>
  );
}
