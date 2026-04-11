import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuthStore } from '../../store/auth';
import { IBApplications } from './IBApplications';
import { IBCommissions } from './IBCommissions';
import { IBDashboard } from './IBDashboard';
import { IBLayout } from './IBLayout';
import { IBNetwork } from './IBNetwork';
import { IBTierRates } from './IBTierRates';
import { IBTokens } from './IBTokens';

export const IBRouter = () => {
  const user = useAuthStore((state) => state.user);
  const canSeeAdminTabs = user?.is_admin === true || user?.role === 'backoffice';

  return (
    <IBLayout>
      <Routes>
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard" element={<IBDashboard />} />
        <Route path="network" element={<IBNetwork />} />
        <Route path="applications" element={<IBApplications />} />
        <Route path="commissions" element={<IBCommissions />} />
        {canSeeAdminTabs && <Route path="tokens" element={<IBTokens />} />}
        {canSeeAdminTabs && <Route path="tier-rates" element={<IBTierRates />} />}
        <Route path="*" element={<Navigate to="dashboard" replace />} />
      </Routes>
    </IBLayout>
  );
};
