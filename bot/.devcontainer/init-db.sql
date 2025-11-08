-- Initialize dYdX Bot Database
-- This script is automatically run when postgres container starts

CREATE SCHEMA IF NOT EXISTS dydx_bot;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- User-facing messages
\echo 'dYdX Trading Bot Database initialized successfully'
\echo 'Database: dydx_bot'
\echo 'User: postgres'
\echo 'Schema: dydx_bot (primary)'
