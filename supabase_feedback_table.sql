-- Таблица для хранения отзывов пользователей
-- Выполнить в Supabase Dashboard → SQL Editor

CREATE TABLE IF NOT EXISTS feedback (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_email TEXT NOT NULL,
  rating INTEGER CHECK (rating >= 1 AND rating <= 5),
  message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индекс для быстрого поиска по email
CREATE INDEX IF NOT EXISTS idx_feedback_user_email ON feedback(user_email);

-- Индекс для сортировки по дате
CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON feedback(created_at DESC);

-- Row Level Security (RLS) — пользователи могут только вставлять свои отзывы
ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;

-- Политика: любой аутентифицированный пользователь может вставить отзыв
CREATE POLICY "Users can insert their own feedback"
  ON feedback
  FOR INSERT
  TO authenticated
  WITH CHECK (true);

-- Политика: только admin может читать все отзывы (опционально)
-- Если хочешь видеть отзывы в Dashboard, эта политика не нужна —
-- Dashboard использует service_role key, который обходит RLS
