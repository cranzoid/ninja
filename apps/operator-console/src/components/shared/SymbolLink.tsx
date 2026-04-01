import Link from 'next/link';
import type { PortfolioLayer } from '@/lib/types';

interface SymbolLinkProps {
  symbol: string;
  layer?: PortfolioLayer;
}

const LAYER_STYLES: Record<PortfolioLayer, { color: string; bg: string; border: string }> = {
  core: {
    color: '#3b82f6',
    bg: 'rgba(59,130,246,0.1)',
    border: 'rgba(59,130,246,0.25)',
  },
  swing: {
    color: '#f59e0b',
    bg: 'rgba(245,158,11,0.1)',
    border: 'rgba(245,158,11,0.25)',
  },
};

export function SymbolLink({ symbol, layer }: SymbolLinkProps) {
  const ls = layer ? LAYER_STYLES[layer] : null;

  return (
    <span className="inline-flex items-center gap-2">
      <Link
        href={`/positions?symbol=${symbol}`}
        className="font-mono font-semibold text-info hover:text-blue-400 transition-colors"
      >
        {symbol}
      </Link>
      {layer && ls && (
        <span
          className="text-2xs font-mono font-semibold tracking-widest uppercase rounded-sm px-1.5 py-0.5"
          style={{
            color: ls.color,
            background: ls.bg,
            border: `1px solid ${ls.border}`,
          }}
        >
          {layer.toUpperCase()}
        </span>
      )}
    </span>
  );
}
