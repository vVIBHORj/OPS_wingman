-- Initialize OpsWingman Database with pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Log successful initialization
DO $$
BEGIN
   RAISE NOTICE 'OpsWingman foundation extensions (vector, uuid-ossp) successfully initialized.';
END $$;
