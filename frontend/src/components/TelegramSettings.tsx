import { TELEGRAM_GLOBAL_ADMIN_ROLES, getUserWorkspaceRole, roleMatches } from '../auth/roles';
import { useAuthStore } from '../store/auth';
import { TelegramGlobalSettings } from './TelegramGlobalSettings';
import { TelegramUserSettings } from './TelegramUserSettings';

export function TelegramSettings() {
  const user = useAuthStore((state) => state.user);
  const role = getUserWorkspaceRole(user);
  const canManageGlobalTelegram = roleMatches(role, TELEGRAM_GLOBAL_ADMIN_ROLES);

  return (
    <div className="space-y-8">
      <TelegramUserSettings />
      {canManageGlobalTelegram && <TelegramGlobalSettings />}
    </div>
  );
}
