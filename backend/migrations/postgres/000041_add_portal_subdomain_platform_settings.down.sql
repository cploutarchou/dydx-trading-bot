DELETE FROM bot_settings
WHERE section = 'platform'
  AND key IN (
    'crm_subdomain_enabled',
    'crm_subdomain_host',
    'ib_subdomain_enabled',
    'ib_subdomain_host'
  );
