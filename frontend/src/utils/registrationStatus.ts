import type { RegistrationStatusResponse } from '../api';

export const ADMIN_DISABLED_REGISTRATION_REASON =
  'Public registration is currently disabled by the administrator';

export const isRegistrationDisabledByAdministrator = (
  status?: RegistrationStatusResponse | null
): boolean =>
  status?.enabled === false &&
  status.mode === 'disabled' &&
  status.reason === ADMIN_DISABLED_REGISTRATION_REASON;
