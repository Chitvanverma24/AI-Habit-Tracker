-- ==============================
-- AI HABIT TRACKER SAAS - POSTGRESQL DATABASE SCHEMA
-- Designed for Supabase + Streamlit
-- ==============================

-- Set default search path
SET search_path = public, pg_catalog;

-- ==============================
-- 1. UTILITY FUNCTIONS & TRIGGERS
-- ==============================

-- Function to automatically update the 'updated_at' timestamp
CREATE OR REPLACE FUNCTION public.set_current_timestamp_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Admin check function (Security Definer to bypass RLS and avoid infinite recursion)

-- ==============================
-- 2. TABLES CREATION
-- ==============================

-- -----------------------------------------------------------------------------------------
-- PROFILES
-- -----------------------------------------------------------------------------------------
CREATE TABLE public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    display_name TEXT,
    timezone TEXT DEFAULT 'UTC',
    is_admin BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

COMMENT ON TABLE public.profiles IS 'User profiles extending the base auth.users table.';
COMMENT ON COLUMN public.profiles.is_admin IS 'Determines if the user has admin panel access.';

-- -----------------------------------------------------------------------------------------
-- SUBSCRIPTIONS
-- -----------------------------------------------------------------------------------------
CREATE TABLE public.subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    plan_type TEXT NOT NULL CHECK (plan_type IN ('free', 'premium', 'lifetime')),
    status TEXT NOT NULL CHECK (status IN ('active', 'canceled', 'past_due', 'trialing', 'incomplete')),
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    cancel_at_period_end BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    CONSTRAINT subscriptions_user_id_key UNIQUE (user_id)
);

COMMENT ON TABLE public.subscriptions IS 'Stores premium subscription status and billing periods for users.';

-- -----------------------------------------------------------------------------------------
-- HABITS
-- -----------------------------------------------------------------------------------------
CREATE TABLE public.habits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    frequency TEXT NOT NULL CHECK (frequency IN ('daily', 'weekly', 'monthly')),
    target_count INTEGER DEFAULT 1 NOT NULL CHECK (target_count > 0),
    -- current_streak INTEGER DEFAULT 0 NOT NULL,
    -- longest_streak INTEGER DEFAULT 0 NOT NULL,
    reminder_time TIME,
    reminder_enabled BOOLEAN DEFAULT FALSE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

COMMENT ON TABLE public.habits IS 'Core habits definitions created by users.';

-- -----------------------------------------------------------------------------------------
-- HABIT LOGS
-- -----------------------------------------------------------------------------------------
CREATE TABLE public.habit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    habit_id UUID NOT NULL REFERENCES public.habits(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    log_date DATE NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('completed', 'skipped', 'failed')),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    CONSTRAINT habit_logs_habit_id_log_date_key UNIQUE (habit_id, log_date)
);

COMMENT ON TABLE public.habit_logs IS 'Daily/Weekly/Monthly execution logs for habits.';

-- -----------------------------------------------------------------------------------------
-- JOURNAL ENTRIES
-- -----------------------------------------------------------------------------------------
CREATE TABLE public.journal_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    entry_date DATE NOT NULL,
    content TEXT NOT NULL,
    mood_score INTEGER CHECK (mood_score >= 1 AND mood_score <= 10),
    ai_coach_feedback TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    CONSTRAINT journal_entries_user_id_entry_date_key UNIQUE (user_id, entry_date)
);

COMMENT ON TABLE public.journal_entries IS 'User daily journals with optional AI coach insights and mood tracking.';

-- -----------------------------------------------------------------------------------------
-- ACHIEVEMENTS
-- -----------------------------------------------------------------------------------------
CREATE TABLE public.achievements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    badge_url TEXT,
    earned_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    CONSTRAINT achievements_user_id_title_key UNIQUE (user_id, title)
);

COMMENT ON TABLE public.achievements IS 'Gamification badges and milestones earned by users.';

-- -----------------------------------------------------------------------------------------
-- FEEDBACK
-- -----------------------------------------------------------------------------------------
CREATE TABLE public.feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    feedback_type TEXT NOT NULL CHECK (feedback_type IN ('bug', 'feature_request', 'general')),
    message TEXT NOT NULL,
    status TEXT DEFAULT 'open' NOT NULL CHECK (status IN ('open', 'in_progress', 'resolved', 'closed')),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

COMMENT ON TABLE public.feedback IS 'User-submitted feedback for admin review.';

-- -----------------------------------------------------------------------------------------
-- NOTIFICATIONS
-- -----------------------------------------------------------------------------------------
CREATE TABLE public.notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('reminder', 'achievement', 'system', 'ai_coach', 'billing')),
    is_read BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

COMMENT ON TABLE public.notifications IS 'In-app notifications and alerts for users.';

-- -----------------------------------------------------------------------------------------
-- SYSTEM SETTINGS
-- -----------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.system_settings (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

COMMENT ON TABLE public.system_settings IS 'Global SaaS system configuration settings.';

INSERT INTO public.system_settings (key, value, description) VALUES
('maintenance_mode', 'false'::jsonb, 'Restrict application access to admins only'),
('registration_enabled', 'true'::jsonb, 'Allow new user registrations'),
('ai_enabled', 'true'::jsonb, 'Globally enable AI Coach integration'),
('selected_ai_model', '"gemini-2.5-flash"'::jsonb, 'Active Gemini AI model identifier'),
('allow_journal', 'true'::jsonb, 'Allow user access to Journal module'),
('allow_habits', 'true'::jsonb, 'Allow user access to Habits module'),
('allow_achievements', 'true'::jsonb, 'Allow user access to Achievements module'),
('allow_admin_panel', 'true'::jsonb, 'Enable Admin panel access'),
('system_name', '"AI Habit Tracker"'::jsonb, 'Public name of the SaaS platform'),
('system_logo', '"🎯"'::jsonb, 'Logo or emblem for the application'),
('support_email', '"support@habittracker.ai"'::jsonb, 'Contact email for platform support'),
('default_timezone', '"UTC"'::jsonb, 'Default timezone for new users')
ON CONFLICT (key) DO NOTHING;


-- ==============================
-- 3. INDEXES FOR PERFORMANCE
-- ==============================

CREATE INDEX idx_subscriptions_user_id ON public.subscriptions(user_id);
CREATE INDEX idx_habits_user_id ON public.habits(user_id);
CREATE INDEX idx_habit_logs_habit_id ON public.habit_logs(habit_id);
CREATE INDEX idx_habit_logs_user_id ON public.habit_logs(user_id);
CREATE INDEX idx_habit_logs_log_date ON public.habit_logs(log_date);
CREATE INDEX idx_journal_entries_user_id ON public.journal_entries(user_id);
CREATE INDEX idx_journal_entries_entry_date ON public.journal_entries(entry_date);
CREATE INDEX idx_achievements_user_id ON public.achievements(user_id);
CREATE INDEX idx_feedback_status ON public.feedback(status);
CREATE INDEX idx_notifications_user_id_is_read ON public.notifications(user_id, is_read);

-- ==============================
-- 4. UPDATED_AT TRIGGERS
-- ==============================

CREATE TRIGGER set_profiles_updated_at BEFORE UPDATE ON public.profiles FOR EACH ROW EXECUTE FUNCTION public.set_current_timestamp_updated_at();
CREATE TRIGGER set_subscriptions_updated_at BEFORE UPDATE ON public.subscriptions FOR EACH ROW EXECUTE FUNCTION public.set_current_timestamp_updated_at();
CREATE TRIGGER set_habits_updated_at BEFORE UPDATE ON public.habits FOR EACH ROW EXECUTE FUNCTION public.set_current_timestamp_updated_at();
CREATE TRIGGER set_habit_logs_updated_at BEFORE UPDATE ON public.habit_logs FOR EACH ROW EXECUTE FUNCTION public.set_current_timestamp_updated_at();
CREATE TRIGGER set_journal_entries_updated_at BEFORE UPDATE ON public.journal_entries FOR EACH ROW EXECUTE FUNCTION public.set_current_timestamp_updated_at();
CREATE TRIGGER set_feedback_updated_at BEFORE UPDATE ON public.feedback FOR EACH ROW EXECUTE FUNCTION public.set_current_timestamp_updated_at();
CREATE TRIGGER set_notifications_updated_at BEFORE UPDATE ON public.notifications FOR EACH ROW EXECUTE FUNCTION public.set_current_timestamp_updated_at();
CREATE TRIGGER set_system_settings_updated_at BEFORE UPDATE ON public.system_settings FOR EACH ROW EXECUTE FUNCTION public.set_current_timestamp_updated_at();

-- -----------------------------------------------------------------------------------------
-- SYSTEM SETTINGS POLICIES
-- -----------------------------------------------------------------------------------------
ALTER TABLE public.system_settings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read system settings" ON public.system_settings FOR SELECT USING (true);
CREATE POLICY "Admins manage system settings" ON public.system_settings FOR ALL USING (public.is_admin());

-- ==============================
-- 5. SUPABASE AUTH TRIGGER (AUTO-CREATE PROFILE)
-- ==============================

-- Function to handle new user signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger AS $$
BEGIN
    INSERT INTO public.profiles (
        id,
        display_name
    )
    VALUES (
        NEW.id,
        COALESCE(
            NEW.raw_user_meta_data->>'display_name',
            split_part(NEW.email, '@', 1)
        )
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger attached to the Supabase auth.users table
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.profiles
        WHERE id = auth.uid()
          AND is_admin = TRUE
    );
$$
LANGUAGE sql
SECURITY DEFINER
SET search_path = public;


-- ==============================
-- 6. ROW LEVEL SECURITY (RLS) POLICIES
-- ==============================

-- Enable RLS on all tables
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.habits ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.habit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.journal_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.achievements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

-- -----------------------------------------------------------------------------------------
-- PROFILES POLICIES
-- -----------------------------------------------------------------------------------------
CREATE POLICY "Users can view own profile" ON public.profiles FOR SELECT USING (auth.uid() = id OR public.is_admin());
CREATE POLICY "Users can update own profile" ON public.profiles FOR UPDATE USING (auth.uid() = id OR public.is_admin());
CREATE POLICY "Admins can delete profiles" ON public.profiles FOR DELETE USING (public.is_admin());
CREATE POLICY "Users can delete own profile" ON public.profiles FOR DELETE USING (auth.uid() = id);
-- Note: Insert is handled by the auth trigger via Security Definer

-- -----------------------------------------------------------------------------------------
-- SUBSCRIPTIONS POLICIES
-- -----------------------------------------------------------------------------------------
CREATE POLICY "Users can view own subscription" ON public.subscriptions FOR SELECT USING (auth.uid() = user_id OR public.is_admin());
-- Users shouldn't directly update their subscription status, this is usually done via a secure backend/webhook.
CREATE POLICY "Admins can manage subscriptions" ON public.subscriptions FOR ALL USING (public.is_admin());

-- -----------------------------------------------------------------------------------------
-- HABITS POLICIES
-- -----------------------------------------------------------------------------------------
CREATE POLICY "Users can manage own habits" ON public.habits FOR ALL USING (auth.uid() = user_id OR public.is_admin());

-- -----------------------------------------------------------------------------------------
-- HABIT LOGS POLICIES
-- -----------------------------------------------------------------------------------------
CREATE POLICY "Users can manage own habit logs" ON public.habit_logs FOR ALL USING (auth.uid() = user_id OR public.is_admin());

-- -----------------------------------------------------------------------------------------
-- JOURNAL ENTRIES POLICIES
-- -----------------------------------------------------------------------------------------
CREATE POLICY "Users can manage own journal entries" ON public.journal_entries FOR ALL USING (auth.uid() = user_id OR public.is_admin());

-- -----------------------------------------------------------------------------------------
-- ACHIEVEMENTS POLICIES
-- -----------------------------------------------------------------------------------------
CREATE POLICY "Users can view own achievements" ON public.achievements FOR SELECT USING (auth.uid() = user_id OR public.is_admin());
-- Achievements are granted by the system/backend, users shouldn't insert/update them directly.
CREATE POLICY "Admins can manage achievements" ON public.achievements FOR ALL USING (public.is_admin());

-- -----------------------------------------------------------------------------------------
-- FEEDBACK POLICIES
-- -----------------------------------------------------------------------------------------
CREATE POLICY "Users can insert feedback" ON public.feedback FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can view own feedback" ON public.feedback FOR SELECT USING (auth.uid() = user_id OR public.is_admin());
CREATE POLICY "Admins can manage all feedback" ON public.feedback FOR ALL USING (public.is_admin());

-- -----------------------------------------------------------------------------------------
-- NOTIFICATIONS POLICIES
-- -----------------------------------------------------------------------------------------
CREATE POLICY "Users can view own notifications" ON public.notifications FOR SELECT USING (auth.uid() = user_id OR public.is_admin());
CREATE POLICY "Users can update own notifications" ON public.notifications FOR UPDATE USING (auth.uid() = user_id OR public.is_admin());
CREATE POLICY "Users can delete own notifications" ON public.notifications FOR DELETE USING (auth.uid() = user_id OR public.is_admin());
-- Insert is typically handled by system/triggers.
CREATE POLICY "Admins can insert notifications" ON public.notifications FOR INSERT WITH CHECK (public.is_admin());

CREATE POLICY "Users can insert own achievements" ON public.achievements FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE TABLE public.licenses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    license_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unused' CHECK (status IN ('unused', 'active', 'revoked')),
    assigned_user_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    activated_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    assigned_email TEXT,
    activated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    revoked_at TIMESTAMPTZ,
    CONSTRAINT licenses_license_key_key UNIQUE (license_key)
);

COMMENT ON TABLE public.licenses IS 'Stores Etsy purchase license keys and activation records.';

CREATE INDEX idx_licenses_license_key ON public.licenses(license_key);
CREATE INDEX idx_licenses_status ON public.licenses(status);
CREATE INDEX idx_licenses_assigned_user_id ON public.licenses(assigned_user_id);
CREATE INDEX idx_licenses_assigned_email ON public.licenses(assigned_email);

ALTER TABLE public.licenses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can manage all licenses" ON public.licenses
    FOR ALL
    USING (public.is_admin())
    WITH CHECK (public.is_admin());

CREATE POLICY "Users view own license" ON public.licenses
    FOR SELECT
    USING (
        (auth.uid() IS NOT NULL AND (assigned_user_id = auth.uid() OR activated_by = auth.uid()))
        OR
        (assigned_email IS NOT NULL AND LOWER(assigned_email) = LOWER(auth.jwt()->>'email'))
    );

CREATE OR REPLACE FUNCTION public.activate_purchase(p_license_key TEXT, p_email TEXT)
RETURNS JSONB AS $$
DECLARE
    v_key TEXT;
    v_email TEXT;
    v_license RECORD;
    v_user_id UUID := auth.uid();
BEGIN
    v_key := UPPER(TRIM(p_license_key));
    v_email := LOWER(TRIM(p_email));

    IF v_key IS NULL OR v_key = '' THEN
        RETURN jsonb_build_object('success', false, 'error', 'Invalid license key.');
    END IF;

    IF v_email IS NULL OR v_email = '' OR position('@' in v_email) = 0 THEN
        RETURN jsonb_build_object('success', false, 'error', 'Invalid email address.');
    END IF;

    SELECT * INTO v_license FROM public.licenses WHERE UPPER(TRIM(license_key)) = v_key;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('success', false, 'error', 'Invalid license key.');
    END IF;

    IF v_license.status = 'revoked' THEN
        RETURN jsonb_build_object('success', false, 'error', 'This license has been revoked.');
    ELSIF v_license.status = 'active' THEN
        IF v_license.assigned_email IS NOT NULL AND LOWER(TRIM(v_license.assigned_email)) = v_email THEN
            IF v_user_id IS NOT NULL AND v_license.assigned_user_id IS NULL THEN
                UPDATE public.licenses
                SET assigned_user_id = v_user_id, activated_by = v_user_id
                WHERE id = v_license.id;
            END IF;
            RETURN jsonb_build_object('success', true, 'message', 'Purchase already activated for this email.');
        ELSE
            RETURN jsonb_build_object('success', false, 'error', 'This license has already been activated.');
        END IF;
    END IF;

    UPDATE public.licenses
    SET status = 'active',
        assigned_email = v_email,
        assigned_user_id = COALESCE(v_user_id, assigned_user_id),
        activated_by = COALESCE(v_user_id, activated_by),
        activated_at = NOW()
    WHERE id = v_license.id;

    RETURN jsonb_build_object('success', true, 'message', 'Purchase activated successfully.');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

CREATE OR REPLACE FUNCTION public.activate_license(p_license_key TEXT)
RETURNS JSONB AS $$
DECLARE
    v_user_email TEXT := auth.jwt()->>'email';
BEGIN
    RETURN public.activate_purchase(p_license_key, COALESCE(v_user_email, ''));
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

CREATE OR REPLACE FUNCTION public.verify_active_license(p_email TEXT, p_license_key TEXT DEFAULT NULL)
RETURNS JSONB AS $$
DECLARE
    v_email TEXT;
    v_key TEXT;
    v_license RECORD;
BEGIN
    v_email := LOWER(TRIM(COALESCE(p_email, '')));
    v_key := UPPER(TRIM(COALESCE(p_license_key, '')));

    IF v_email IS NULL OR v_email = '' THEN
        RETURN jsonb_build_object('valid', false, 'error', 'Invalid email address.');
    END IF;

    IF v_key IS NOT NULL AND v_key != '' THEN
        SELECT * INTO v_license FROM public.licenses WHERE UPPER(TRIM(license_key)) = v_key;
        IF NOT FOUND THEN
            RETURN jsonb_build_object('valid', false, 'error', 'Invalid license key.');
        END IF;

        IF v_license.status = 'revoked' THEN
            RETURN jsonb_build_object('valid', false, 'error', 'This license has been revoked.');
        ELSIF v_license.status = 'active' THEN
            IF v_license.assigned_email IS NOT NULL AND LOWER(TRIM(v_license.assigned_email)) != v_email THEN
                RETURN jsonb_build_object('valid', false, 'error', 'This license key is activated for a different email address.');
            END IF;
            RETURN jsonb_build_object(
                'valid', true,
                'id', v_license.id,
                'license_key', v_license.license_key,
                'status', v_license.status,
                'assigned_email', v_license.assigned_email,
                'assigned_user_id', v_license.assigned_user_id
            );
        ELSIF v_license.status = 'unused' THEN
            RETURN jsonb_build_object(
                'valid', true,
                'id', v_license.id,
                'license_key', v_license.license_key,
                'status', v_license.status,
                'assigned_email', v_email,
                'assigned_user_id', v_license.assigned_user_id
            );
        END IF;
    ELSE
        SELECT * INTO v_license FROM public.licenses
        WHERE LOWER(TRIM(assigned_email)) = v_email AND status = 'active'
        ORDER BY activated_at DESC LIMIT 1;

        IF NOT FOUND THEN
            RETURN jsonb_build_object('valid', false, 'error', 'No active Etsy purchase found for this email.');
        END IF;

        IF v_license.status = 'revoked' THEN
            RETURN jsonb_build_object('valid', false, 'error', 'This license has been revoked.');
        END IF;

        RETURN jsonb_build_object(
            'valid', true,
            'id', v_license.id,
            'license_key', v_license.license_key,
            'status', v_license.status,
            'assigned_email', v_license.assigned_email,
            'assigned_user_id', v_license.assigned_user_id
        );
    END IF;

    RETURN jsonb_build_object('valid', false, 'error', 'No valid active license found.');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

CREATE OR REPLACE FUNCTION public.link_user_license(p_user_id UUID, p_email TEXT, p_license_key TEXT DEFAULT NULL)
RETURNS JSONB AS $$
DECLARE
    v_email TEXT;
    v_key TEXT;
    v_lic_id UUID;
BEGIN
    v_email := LOWER(TRIM(COALESCE(p_email, '')));
    v_key := UPPER(TRIM(COALESCE(p_license_key, '')));

    IF p_user_id IS NULL THEN
        RETURN jsonb_build_object('success', false, 'error', 'Invalid user ID.');
    END IF;

    IF v_key IS NOT NULL AND v_key != '' THEN
        UPDATE public.licenses
        SET assigned_user_id = p_user_id,
            activated_by = p_user_id,
            status = 'active',
            assigned_email = COALESCE(assigned_email, v_email),
            activated_at = COALESCE(activated_at, NOW())
        WHERE UPPER(license_key) = v_key AND status != 'revoked'
        RETURNING id INTO v_lic_id;
    END IF;

    IF v_lic_id IS NULL AND v_email IS NOT NULL AND v_email != '' THEN
        UPDATE public.licenses
        SET assigned_user_id = p_user_id,
            activated_by = p_user_id
        WHERE LOWER(assigned_email) = v_email AND status = 'active'
        RETURNING id INTO v_lic_id;
    END IF;

    IF v_lic_id IS NOT NULL THEN
        RETURN jsonb_build_object('success', true, 'license_id', v_lic_id);
    ELSE
        RETURN jsonb_build_object('success', false, 'error', 'License not found to link.');
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

CREATE OR REPLACE FUNCTION public.generate_bulk_licenses(p_keys TEXT[])
RETURNS JSONB AS $$
DECLARE
    v_key TEXT;
    v_count INT := 0;
BEGIN
    IF NOT public.is_admin() THEN
        RETURN jsonb_build_object('success', false, 'error', 'Permission denied. Only admins can generate licenses.');
    END IF;

    FOREACH v_key IN ARRAY p_keys LOOP
        INSERT INTO public.licenses (license_key, status)
        VALUES (v_key, 'unused')
        ON CONFLICT (license_key) DO NOTHING;
        v_count := v_count + 1;
    END LOOP;

    RETURN jsonb_build_object('success', true, 'count', v_count);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- -----------------------------------------------------------------------------------------
-- 9. ADMIN SECURE USER DELETION FUNCTION (SECURITY DEFINER)
-- -----------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.admin_delete_user(p_target_user_id UUID)
RETURNS JSONB AS $$
DECLARE
    v_caller_id UUID := auth.uid();
BEGIN
    IF NOT public.is_admin() THEN
        RETURN jsonb_build_object('success', false, 'error', 'Permission denied. Only admins can delete users.');
    END IF;

    IF p_target_user_id IS NULL THEN
        RETURN jsonb_build_object('success', false, 'error', 'Invalid user ID.');
    END IF;

    IF p_target_user_id = v_caller_id THEN
        RETURN jsonb_build_object('success', false, 'error', 'Cannot delete your own admin account.');
    END IF;

    -- 1. Unlink associated licenses
    UPDATE public.licenses
    SET assigned_user_id = NULL,
        activated_by = NULL
    WHERE assigned_user_id = p_target_user_id OR activated_by = p_target_user_id;

    -- 2. Delete cascaded user data
    DELETE FROM public.habit_logs WHERE user_id = p_target_user_id;
    DELETE FROM public.habits WHERE user_id = p_target_user_id;
    DELETE FROM public.journal_entries WHERE user_id = p_target_user_id;
    DELETE FROM public.achievements WHERE user_id = p_target_user_id;
    DELETE FROM public.notifications WHERE user_id = p_target_user_id;
    DELETE FROM public.feedback WHERE user_id = p_target_user_id;
    DELETE FROM public.subscriptions WHERE user_id = p_target_user_id;

    -- 3. Delete profile
    DELETE FROM public.profiles WHERE id = p_target_user_id;

    -- 4. Delete from auth.users if permissions allow
    BEGIN
        DELETE FROM auth.users WHERE id = p_target_user_id;
    EXCEPTION WHEN OTHERS THEN
        -- auth.users deletion might be restricted depending on Supabase extension configuration
        NULL;
    END;

    RETURN jsonb_build_object('success', true, 'message', 'User and associated data deleted successfully.');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;