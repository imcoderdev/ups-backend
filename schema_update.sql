-- Step 1: Remove columns we no longer use
ALTER TABLE public.readings DROP COLUMN IF EXISTS iin;
ALTER TABLE public.readings DROP COLUMN IF EXISTS iout;

-- Step 2: Update ups_status default to match new values
ALTER TABLE public.readings 
  ALTER COLUMN ups_status SET DEFAULT 'UPS ON';

-- Step 3: Add a comment on load column to document it is watts
COMMENT ON COLUMN public.readings.load IS 'Load in Watts (W)';

-- Step 4: Verify final structure
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'readings' 
ORDER BY ordinal_position;
