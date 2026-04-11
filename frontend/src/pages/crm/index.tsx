import { Navigate, Route, Routes } from 'react-router-dom';
import { CRMClientDetail } from './CRMClientDetail';
import { CRMClients } from './CRMClients';
import { CRMCommissions } from './CRMCommissions';
import { CRMDashboard } from './CRMDashboard';
import { CRMHierarchy } from './CRMHierarchy';
import { CRMLayout } from './CRMLayout';
import { CRMPipeline } from './CRMPipeline';
import { CRMSecurity } from './CRMSecurity';

export const CRMRouter = () => (
  <CRMLayout>
    <Routes>
      <Route index element={<Navigate to="dashboard" replace />} />
      <Route path="dashboard" element={<CRMDashboard />} />
      <Route path="clients" element={<CRMClients />} />
      <Route path="clients/:id" element={<CRMClientDetail />} />
      <Route path="pipeline" element={<CRMPipeline />} />
      <Route path="hierarchy" element={<CRMHierarchy />} />
      <Route path="commissions" element={<CRMCommissions />} />
      <Route path="security" element={<CRMSecurity />} />
      <Route path="*" element={<Navigate to="dashboard" replace />} />
    </Routes>
  </CRMLayout>
);
