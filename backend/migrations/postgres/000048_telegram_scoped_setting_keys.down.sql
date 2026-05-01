UPDATE bot_settings
SET key = 'chat_id',
    description = 'Telegram chat id for shared platform notifications',
    updated_at = CURRENT_TIMESTAMP
WHERE section = 'telegram'
  AND key = 'telegram_chat_id_global'
  AND NOT EXISTS (
    SELECT 1
    FROM bot_settings AS legacy
    WHERE legacy.section = 'telegram'
      AND legacy.key = 'chat_id'
  );

UPDATE bot_settings
SET key = 'chat_id_user_' || substr(key, length('telegram_chat_id_user_') + 1),
    description = 'Telegram chat id for user notifications',
    updated_at = CURRENT_TIMESTAMP
WHERE section = 'telegram'
  AND key LIKE 'telegram_chat_id_user_%'
  AND NOT EXISTS (
    SELECT 1
    FROM bot_settings AS legacy
    WHERE legacy.section = 'telegram'
      AND legacy.key = 'chat_id_user_' || substr(bot_settings.key, length('telegram_chat_id_user_') + 1)
  );
