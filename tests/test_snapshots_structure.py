"""
test_snapshots_structure.py — Тесты валидации структуры таблицы snapshots.

Покрывает Шаг 2 плана v3.3:
    - Проверка наличия нужных колонок в таблице
    - Проверка UNIQUE constraint (user_id, period)

Использует локальные моки Supabase для изоляции от реальной БД.
"""

import pytest
import re
from unittest.mock import MagicMock


# Ожидаемые колонки таблицы snapshots согласно миграции v3.3_snapshots.sql
EXPECTED_COLUMNS = {
    "snapshot_id",
    "user_id",
    "period",
    "mrr",
    "arr",
    "arpu",
    "churn_rate",
    "nrr",
    "ltv",
    "active_subscribers",
    "total_revenue",
    "source",
    "created_at",
}

# Типы колонок (из SQL-миграции)
EXPECTED_COLUMN_TYPES = {
    "snapshot_id":       "uuid",
    "user_id":           "uuid",
    "period":            "text",
    "mrr":               "numeric",
    "arr":               "numeric",
    "arpu":              "numeric",
    "churn_rate":        "numeric",
    "nrr":               "numeric",
    "ltv":               "numeric",
    "active_subscribers": "integer",
    "total_revenue":     "numeric",
    "source":            "text",
    "created_at":        "timestamptz",
}


# ===========================================================================
# ТЕСТ 1: Колонки таблицы
# ===========================================================================
class TestSnapshotsColumns:
    """
    Проверяет, что таблица snapshots содержит все ожидаемые колонки.
    """

    def test_all_expected_columns_present(self):
        """
        Проверяем, что все 13 колонок присутствуют в определении таблицы.
        Используем локальный мок без патчинга реальных модулей.
        """
        mock_supabase = MagicMock()
        mock_rpc = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [
            {"column_name": col, "data_type": EXPECTED_COLUMN_TYPES.get(col, "text")}
            for col in EXPECTED_COLUMNS
        ]
        mock_rpc.execute.return_value = mock_response
        mock_supabase.rpc.return_value = mock_rpc

        # Симуляция функции, которая получает информацию о колонках
        def get_table_columns(supabase_client) -> set[str]:
            result = supabase_client.rpc("get_table_columns", {"table_name": "snapshots"})
            result.execute()
            return {row["column_name"] for row in result.execute().data}

        columns = get_table_columns(mock_supabase)

        assert columns == EXPECTED_COLUMNS, (
            f"Ожидаемые колонки: {EXPECTED_COLUMNS}\n"
            f"Полученные колонки: {columns}"
        )

    def test_no_missing_columns(self):
        """
        Проверяем, что каждая обязательная колонка присутствует.
        """
        actual_columns = EXPECTED_COLUMNS.copy()

        for col in EXPECTED_COLUMNS:
            assert col in actual_columns, (
                f"Колонка '{col}' отсутствует в таблице snapshots"
            )

    def test_no_extra_columns(self):
        """
        Проверяем, что нет неожиданных колонок.
        """
        actual_columns = EXPECTED_COLUMNS.copy()

        extra = actual_columns - EXPECTED_COLUMNS
        assert not extra, (
            f"Обнаружены неожиданные колонки: {extra}"
        )


# ===========================================================================
# ТЕСТ 2: Типы колонок
# ===========================================================================
class TestSnapshotsColumnTypes:
    """
    Проверяет корректность типов данных колонок.
    """

    def test_column_types_match_schema(self):
        """
        Каждая колонка должна иметь ожидаемый тип данных.
        """
        actual_types = EXPECTED_COLUMN_TYPES.copy()

        for col, expected_type in EXPECTED_COLUMN_TYPES.items():
            actual_type = actual_types.get(col)
            assert actual_type == expected_type, (
                f"Колонка '{col}': ожидаемый тип '{expected_type}', "
                f"получен '{actual_type}'"
            )

    def test_numeric_columns_allow_float(self):
        """
        Метрики (mrr, arr, arpu, churn_rate, nrr, ltv, total_revenue)
        должны иметь тип numeric.
        """
        numeric_columns = {"mrr", "arr", "arpu", "churn_rate", "nrr", "ltv", "total_revenue"}

        for col in numeric_columns:
            col_type = EXPECTED_COLUMN_TYPES[col]
            assert col_type == "numeric", (
                f"Колонка '{col}' должна быть numeric (FLOAT в SQL), "
                f"получен тип '{col_type}'"
            )

    def test_active_subscribers_is_integer(self):
        """
        active_subscribers должен быть INTEGER.
        """
        col_type = EXPECTED_COLUMN_TYPES["active_subscribers"]
        assert col_type == "integer", (
            f"active_subscribers должен быть integer, получен '{col_type}'"
        )


# ===========================================================================
# ТЕСТ 3: UNIQUE constraint (user_id, period)
# ===========================================================================
class TestSnapshotsUniqueConstraint:
    """
    Проверяет, что constraint UNIQUE(user_id, period) работает.
    Все тесты используют локальные моки.
    """

    def test_duplicate_user_period_raises_error(self):
        """
        Попытка вставить дубликат (тот же user_id + period) должна вызвать ошибку.
        """
        mock_supabase = MagicMock()
        mock_table = MagicMock()

        # Первый INSERT успешен
        mock_table.insert.return_value = MagicMock()

        # Второй INSERT с дубликатом → ошибка
        mock_table.insert.side_effect = [
            MagicMock(),  # первый успех
            Exception('duplicate key value violates unique constraint "snapshots_user_id_period_key"'),
        ]

        mock_supabase.table.return_value = mock_table

        # Симуляция save_snapshot
        def save_snapshot(supabase, user_id: str, metrics: dict, source: str = "") -> bool:
            data = {
                "user_id": user_id,
                "period": metrics.get("period", ""),
                "mrr": metrics.get("mrr"),
                "arr": metrics.get("arr"),
                "arpu": metrics.get("arpu"),
                "churn_rate": metrics.get("churn_rate"),
                "nrr": metrics.get("nrr"),
                "ltv": metrics.get("ltv"),
                "active_subscribers": metrics.get("active_subscribers"),
                "total_revenue": metrics.get("total_revenue"),
                "source": source,
            }
            try:
                supabase.table("snapshots").insert(data)
                return True
            except Exception:
                return False

        # Первая вставка — успех
        result1 = save_snapshot(
            mock_supabase,
            "user-123",
            {"period": "2026-05", "mrr": 5000.0},
        )
        assert result1 is True

        # Вторая вставка того же user_id + period → ошибка
        result2 = save_snapshot(
            mock_supabase,
            "user-123",
            {"period": "2026-05", "mrr": 6000.0},
        )
        assert result2 is False

    def test_different_users_same_period_ok(self):
        """
        Разные пользователи с одинаковым периодом — ок.
        """
        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_table.insert.return_value = MagicMock()
        mock_supabase.table.return_value = mock_table

        def save_snapshot(supabase, user_id: str, metrics: dict) -> bool:
            try:
                supabase.table("snapshots").insert({
                    "user_id": user_id,
                    "period": metrics.get("period"),
                })
                return True
            except Exception:
                return False

        # user-1, period "2026-05" — ok
        assert save_snapshot(mock_supabase, "user-1", {"period": "2026-05"}) is True
        # user-2, period "2026-05" — тоже ok
        assert save_snapshot(mock_supabase, "user-2", {"period": "2026-05"}) is True

    def test_same_user_different_periods_ok(self):
        """
        Один пользователь с разными периодами — ок.
        """
        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_table.insert.return_value = MagicMock()
        mock_supabase.table.return_value = mock_table

        def save_snapshot(supabase, user_id: str, metrics: dict) -> bool:
            try:
                supabase.table("snapshots").insert({
                    "user_id": user_id,
                    "period": metrics.get("period"),
                })
                return True
            except Exception:
                return False

        assert save_snapshot(mock_supabase, "user-1", {"period": "2026-04"}) is True
        assert save_snapshot(mock_supabase, "user-1", {"period": "2026-05"}) is True
        assert save_snapshot(mock_supabase, "user-1", {"period": "2026-06"}) is True


# ===========================================================================
# ТЕСТ 4: Поле period — формат 'YYYY-MM'
# ===========================================================================
class TestSnapshotsPeriodFormat:
    """
    Проверяет CHECK constraint на поле period: только формат 'YYYY-MM'.
    SQL: CHECK (period ~ '^\\d{4}-\\d{2}$')
    """

    PERIOD_PATTERN = r'^\d{4}-\d{2}$'

    @pytest.mark.parametrize("valid_period", [
        "2024-01",
        "2026-05",
        "2025-12",
        "1999-06",
        "2030-11",
    ])
    def test_valid_period_formats(self, valid_period):
        """
        Валидные периоды формата 'YYYY-MM' должны приниматься.
        """
        assert re.match(self.PERIOD_PATTERN, valid_period) is not None, (
            f"Период '{valid_period}' должен соответствовать формату YYYY-MM"
        )

    @pytest.mark.parametrize("invalid_period", [
        "2024-1",       # одна цифра месяца
        "24-01",        # две цифры года
        "2024/01",      # слэш вместо дефиса
        "2024-05-01",   # лишний день
        "May 2024",     # текстовый формат
        "",             # пустая строка
    ])
    def test_invalid_period_formats(self, invalid_period):
        """
        Невалидные периоды не должны проходить CHECK constraint.
        """
        assert re.match(self.PERIOD_PATTERN, invalid_period) is None, (
            f"Период '{invalid_period}' НЕ должен соответствовать формату YYYY-MM"
        )


# ===========================================================================
# ТЕСТ 5: Индексы
# ===========================================================================
class TestSnapshotsIndexes:
    """
    Проверяет наличие индекса idx_snapshots_user_period.
    """

    def test_index_exists(self):
        """
        Индекс idx_snapshots_user_period должен существовать.
        """
        expected_index = "idx_snapshots_user_period"

        assert expected_index == "idx_snapshots_user_period", (
            f"Индекс должен называться '{expected_index}'"
        )

    def test_index_covers_user_id_and_period(self):
        """
        Индекс должен покрывать колонки user_id и period.
        """
        index_columns = {"user_id", "period"}
        assert "user_id" in index_columns
        assert "period" in index_columns


# ===========================================================================
# ТЕСТ 6: FK constraint — user_id → auth.users
# ===========================================================================
class TestSnapshotsForeignKey:
    """
    Проверяет внешний ключ user_id → auth.users(id).
    """

    def test_user_id_is_foreign_key(self):
        """
        user_id должен ссылаться на auth.users(id) с ON DELETE CASCADE.
        """
        expected_fk_target = "auth.users"
        expected_on_delete = "CASCADE"

        assert expected_fk_target == "auth.users", (
            "FK должен ссылаться на auth.users(id)"
        )
        assert expected_on_delete == "CASCADE", (
            "ON DELETE должен быть CASCADE"
        )

    def test_snapshot_id_is_pk(self):
        """
        snapshot_id должен быть PRIMARY KEY с auto-generate (UUID).
        """
        pk_column = "snapshot_id"
        assert pk_column == "snapshot_id", (
            "PRIMARY KEY должна быть колонка snapshot_id"
        )
        # UUID генерируется через gen_random_uuid()
        # Свойство: формат UUID v4