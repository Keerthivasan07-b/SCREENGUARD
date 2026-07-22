-- ScreenGuard Supabase Database Schema
-- Paste this SQL code directly into the Supabase SQL Editor (https://supabase.com) and click "Run"

-- 1. Create Users Table (Optional local users backup)
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    first_name TEXT,
    last_name TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Enable Row Level Security (RLS) or add public access for rapid hackathon testing
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public read and write access" ON public.users FOR ALL USING (true) WITH CHECK (true);

-- 2. Create Classroom Sessions Table
CREATE TABLE IF NOT EXISTS public.classroom_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_email TEXT NOT NULL,
    classroom TEXT NOT NULL,
    session_title TEXT NOT NULL,
    ai_gaze BOOLEAN DEFAULT true,
    ai_tabs BOOLEAN DEFAULT true,
    ai_objects BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.classroom_sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public read and write access" ON public.classroom_sessions FOR ALL USING (true) WITH CHECK (true);

-- 3. Create Alerts Table
CREATE TABLE IF NOT EXISTS public.alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_title TEXT,
    student_name TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    alert_message TEXT NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.alerts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public read and write access" ON public.alerts FOR ALL USING (true) WITH CHECK (true);
