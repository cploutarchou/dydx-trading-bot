INSERT IGNORE INTO bot_settings (
  section,
  `key`,
  value,
  value_type,
  description,
  default_value,
  is_active,
  version,
  created_at,
  updated_at
)
VALUES (
  'platform',
  'coming_soon_enabled',
  '0',
  'boolean',
  'Show the public Coming Soon launch page while keeping authenticated admin access available',
  '0',
  1,
  1,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
);
