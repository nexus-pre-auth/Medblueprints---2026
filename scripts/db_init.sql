-- MedBlueprints PostgreSQL initialization
-- Tables are created by SQLAlchemy on startup, this script sets up extensions

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search on room labels

-- Index hint for compliance queries
COMMENT ON DATABASE medblueprints IS 'MedBlueprints regulatory intelligence platform';
