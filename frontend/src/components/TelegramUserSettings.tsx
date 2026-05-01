import { UserRound } from 'lucide-react';
import { TelegramScopeSettingsPanel } from './TelegramScopeSettingsPanel';

export function TelegramUserSettings() {
  return (
    <TelegramScopeSettingsPanel
      scope="user"
      icon={UserRound}
      title="My Telegram Notifications"
      description="These are your personal notification settings. Only you can see and modify them."
      tokenTitle="Your bot token"
      chatDescription="Applies to your runtime-managed bot instances."
      defaultLabel="My trading bot"
    />
  );
}
