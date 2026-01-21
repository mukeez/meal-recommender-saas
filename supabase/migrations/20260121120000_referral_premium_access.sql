DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'referral_access_type') THEN
        CREATE TYPE public.referral_access_type AS ENUM ('standard', 'premium_free');
    END IF;
END $$;

ALTER TABLE public.referral_codes
    ADD COLUMN IF NOT EXISTS access_type public.referral_access_type NOT NULL DEFAULT 'standard',
    ADD COLUMN IF NOT EXISTS access_duration_days integer NOT NULL DEFAULT 30,
    ADD COLUMN IF NOT EXISTS activation_date timestamp with time zone,
    ADD COLUMN IF NOT EXISTS assigned_to_user_id uuid,
    ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'referral_codes_assigned_to_user_id_fkey') THEN
        ALTER TABLE ONLY public.referral_codes
            ADD CONSTRAINT referral_codes_assigned_to_user_id_fkey
            FOREIGN KEY (assigned_to_user_id) REFERENCES public.user_profiles(id);
    END IF;
END $$;
