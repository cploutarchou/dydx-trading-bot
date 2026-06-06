INSERT INTO bot_settings (
  section,
  key,
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
  'false',
  'boolean',
  'Show the public Coming Soon launch page while keeping authenticated admin access available',
  'false',
  true,
  1,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
)
ON CONFLICT (section, key) DO NOTHING;
