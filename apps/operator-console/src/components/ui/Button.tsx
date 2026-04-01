type ButtonVariant = 'primary' | 'danger' | 'ghost' | 'outline';

const VARIANTS: Record<ButtonVariant, string> = {
  primary: 'bg-info text-white hover:bg-blue-500',
  danger: 'bg-loss/80 text-white hover:bg-loss border border-loss/40',
  ghost: 'text-white/60 hover:text-white hover:bg-white/[0.04]',
  outline:
    'text-white/60 border border-white/10 hover:text-white hover:border-white/20 hover:bg-white/[0.03]',
};

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  children: React.ReactNode;
}

export function Button({
  variant = 'outline',
  size = 'md',
  loading = false,
  children,
  className = '',
  disabled,
  ...props
}: ButtonProps) {
  const sizeClass =
    size === 'sm'
      ? 'px-3 py-1.5 text-xs'
      : size === 'lg'
      ? 'px-5 py-3 text-sm'
      : 'px-4 py-2 text-sm';

  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={[
        'inline-flex items-center gap-2 rounded-sm font-medium transition-colors cursor-pointer',
        'disabled:opacity-40 disabled:cursor-not-allowed',
        sizeClass,
        VARIANTS[variant],
        className,
      ].join(' ')}
    >
      {loading && (
        <span
          className="inline-block w-3 h-3 rounded-full border-2 border-current border-t-transparent animate-spin"
          aria-hidden
        />
      )}
      {children}
    </button>
  );
}
