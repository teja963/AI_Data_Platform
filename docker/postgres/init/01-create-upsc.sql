SELECT 'CREATE DATABASE upsc_platform_data'
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'upsc_platform_data'
)\gexec
