import type { DashboardData } from '@/lib/types';
import { formatINR, formatINRSigned, pnlColor, safeFloat } from '@/lib/utils';

interface HeaderProps {
  title: string;
  data?: DashboardData | null;
}

export function Header({ title, data }: HeaderProps) {
  const equity = data ? safeFloat(data.portfolio_equity) : null;
  const pnl = data ? safeFloat(data.todays_pnl) : null;

  return (
    <header
      className="flex-shrink-0 flex items-center justify-between px-6"
      style={{
        height: '48px',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        background: 'rgba(10,10,15,0.8)',
        backdropFilter: 'blur(8px)',
        position: 'sticky',
        top: 0,
        zIndex: 10,
      }}
    >
      <h1 className="text-sm font-semibold tracking-wide text-white/80 uppercase">
        {title}
      </h1>

      {data && (
        <div className="flex items-center gap-6">
          {equity !== null && (
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-white/30 uppercase tracking-wider">Equity</span>
              <span className="text-sm font-mono font-semibold text-white/80">
                {formatINR(equity)}
              </span>
            </div>
          )}
          {pnl !== null && (
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-white/30 uppercase tracking-wider">Today</span>
              <span className={`text-sm font-mono font-semibold ${pnlColor(pnl)}`}>
                {formatINRSigned(pnl)}
              </span>
            </div>
          )}
        </div>
      )}
    </header>
  );
}
