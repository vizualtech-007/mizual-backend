-- Migration to update feedback system constraints to 0/1 (thumbs down/up)
-- No existing data to convert, just update constraints

-- For public schema
-- Drop old constraint (1-5 stars) and add new one (0/1)
ALTER TABLE public.edit_feedback 
DROP CONSTRAINT IF EXISTS edit_feedback_rating_check;

ALTER TABLE public.edit_feedback 
ADD CONSTRAINT edit_feedback_rating_check CHECK (rating IN (0, 1));

-- For preview schema  
-- Drop old constraint (1-5 stars) and add new one (0/1)
ALTER TABLE preview.edit_feedback 
DROP CONSTRAINT IF EXISTS edit_feedback_rating_check;

ALTER TABLE preview.edit_feedback 
ADD CONSTRAINT edit_feedback_rating_check CHECK (rating IN (0, 1));

-- Add comment for documentation
COMMENT ON COLUMN public.edit_feedback.rating IS 'User feedback: 0 for thumbs down, 1 for thumbs up';
COMMENT ON COLUMN preview.edit_feedback.rating IS 'User feedback: 0 for thumbs down, 1 for thumbs up';