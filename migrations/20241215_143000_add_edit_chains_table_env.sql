-- Environment-aware migration for edit chains
-- This will be processed by migrate.py to target the correct schema

-- Create edit_chains table in the target schema
CREATE TABLE IF NOT EXISTS TARGET_SCHEMA.edit_chains (
    id SERIAL PRIMARY KEY,
    edit_uuid VARCHAR NOT NULL,
    parent_edit_uuid VARCHAR,
    chain_position INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_edit_chains_edit_uuid_TARGET_SCHEMA ON TARGET_SCHEMA.edit_chains(edit_uuid);
CREATE INDEX IF NOT EXISTS idx_edit_chains_parent_uuid_TARGET_SCHEMA ON TARGET_SCHEMA.edit_chains(parent_edit_uuid);
CREATE INDEX IF NOT EXISTS idx_edit_chains_created_at_TARGET_SCHEMA ON TARGET_SCHEMA.edit_chains(created_at);