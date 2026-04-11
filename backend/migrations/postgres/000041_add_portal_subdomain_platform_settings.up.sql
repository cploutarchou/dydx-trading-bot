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
VALUES
  (
    'platform',
    'crm_subdomain_enabled',
    'true',
    'boolean',
    'Enable CRM subdomain routing shortcuts',
    'true',
    true,
    1,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  ),
  (
    'platform',
    'crm_subdomain_host',
    'crm.localhost',
    'string',
    'CRM subdomain host used for cross-portal links',
    'crm.localhost',
    true,
    1,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  ),
  (
    'platform',
    'ib_subdomain_enabled',
    'true',
    'boolean',
    'Enable IB portal subdomain routing shortcuts',
    'true',
    true,
    1,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  ),
  (
    'platform',
    'ib_subdomain_host',
    'ib-portal.localhost',
    'string',
    'IB portal subdomain host used for cross-portal links',
    'ib-portal.localhost',
    true,
    1,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  )
ON CONFLICT (section, key) DO NOTHING;
