import { Header } from './Header';
import type { DashboardData } from '@/lib/types';

interface PageWrapperProps {
  title: string;
  children: React.ReactNode;
  dashboardData?: DashboardData | null;
}

export function PageWrapper({ title, children, dashboardData }: PageWrapperProps) {
  return (
    <div className="flex flex-col h-full min-h-screen">
      <Header title={title} data={dashboardData} />
      <div className="flex-1 p-6">{children}</div>
    </div>
  );
}
