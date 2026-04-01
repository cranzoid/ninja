import type { Metadata } from 'next';
import './globals.css';
import { Sidebar } from '@/components/layout/Sidebar';

export const metadata: Metadata = {
  title: 'Indian Equities — Operator Console',
  description: 'AI-assisted trading operations console for NSE cash equities',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        {/* Mobile guard */}
        <div className="desktop-only-guard fixed inset-0 z-50 flex-col items-center justify-center bg-console-bg text-white/70 text-center p-8">
          <div className="text-4xl mb-4">◉</div>
          <div className="text-lg font-semibold mb-2">Operations Console</div>
          <div className="text-sm text-white/50 max-w-xs">
            Best viewed on desktop at 1280px or wider. This is an operations
            tool, not a mobile app.
          </div>
        </div>

        {/* Main layout */}
        <div className="main-layout h-screen w-screen overflow-hidden bg-console-bg">
          <Sidebar />
          <main className="flex-1 overflow-y-auto h-screen">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
