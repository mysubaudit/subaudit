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

-- Row Level Security (RLS)
ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;

-- Политика INSERT: пользователь может вставить отзыв ТОЛЬКО от своего email
-- (auth.uid() даёт текущего пользователя, auth.users.email проверяет его email)
CREATE POLICY "users_insert_own_feedback"
  ON feedback
  FOR INSERT
  TO authenticated
  WITH CHECK (
    user_email = (
      SELECT email FROM auth.users WHERE id = auth.uid()
    )
  );

-- Политика SELECT: пользователь может читать ТОЛЬКО свои отзывы
CREATE POLICY "users_read_own_feedback"
  ON feedback
  FOR SELECT
  TO authenticated
  USING (
    user_email = (
      SELECT email FROM auth.users WHERE id = auth.uid()
    )
  );