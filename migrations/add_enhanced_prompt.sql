-- Migration to add enhanced_prompt column to edits table
-- Run this in both public and preview schemas

-- For public schema
ALTER TABLE public.edits ADD COLUMN IF NOT EXISTS enhanced_prompt VARCHAR;

-- For preview schema
ALTER TABLE preview.edits ADD COLUMN IF NOT EXISTS enhanced_prompt VARCHAR;