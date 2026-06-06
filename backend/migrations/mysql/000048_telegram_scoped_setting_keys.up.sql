-- Clarify Telegram bot_settings keys by scope while preserving legacy fallback.
UPDATE bot_settings
SET key = 'telegram_chat_id_global',
    description = 'Telegram chat id for global platform notifications',
    updated_at = CURRENT_TIMESTAMP
WHERE section = 'telegram'
  AND key = 'chat_id'
  AND NOT EXISTS (
    SELECT 1
    FROM bot_settings AS canonical
    WHERE canonical.section = 'telegram'
      AND canonical.key = 'telegram_chat_id_global'
  );

UPDATE bot_settings
SET key = 'telegram_chat_id_user_' || substr(key, length('chat_id_user_') + 1),
    description = 'Telegram chat id for user notifications',
    updated_at = CURRENT_TIMESTAMP
WHERE section = 'telegram'
  AND key LIKE 'chat_id_user_%'
  AND NOT EXISTS (
    SELECT 1
    FROM bot_settings AS canonical
    WHERE canonical.section = 'telegram'
      AND canonical.key = 'telegram_chat_id_user_' || substr(bot_settings.key, length('chat_id_user_') + 1)
  );
