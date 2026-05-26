-- v3.3 Snapshots: сохраняем агрегаты метрик после каждой загрузки CSV
-- Применяется вручную через Supabase SQL Editor
-- Статус миграции: PENDING

CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id       UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id           UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    period            TEXT NOT NULL CHECK (period ~ '^\d{4}-\d{2}$'),
    mrr               FLOAT,
    arr               FLOAT,
    arpu              FLOAT,
    churn_rate        FLOAT,
    nrr               FLOAT,
    ltv               FLOAT,
    active_subscribers INTEGER,
    total_revenue     FLOAT,
    source            TEXT DEFAULT '',
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, period)
);

-- Индекс для быстрой выборки истории пользователя
CREATE INDEX IF NOT EXISTS idx_snapshots_user_period ON snapshots (user_id, period);

-- ── RLS: пользователь видит только свои snapshots ───────────────────────────
ALTER TABLE snapshots ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_see_only_own_snapshots" ON snapshots
    FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);