import { ShieldCheck } from 'lucide-react';
import { TelegramScopeSettingsPanel } from './TelegramScopeSettingsPanel';

export function TelegramGlobalSettings() {
  return (
    <TelegramScopeSettingsPanel
      scope="global"
      icon={ShieldCheck}
      title="Platform Telegram Alerts"
      description="Global Telegram settings for platform-wide alerts and admin notifications."
      badge="Admin only"
      tokenTitle="Platform bot token"
      chatDescription="Used as fallback delivery for runtime-managed bot instances without personal settings."
      defaultLabel="Platform alerts"
    />
  );
}
