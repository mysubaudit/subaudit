"""
test_immutability.py
Spec: Section 17 — «AST NodeVisitor — direct + aliased mutations across app/**/*.py»

Принцип: метрические функции (metrics.py, forecast.py, simulation.py) обязаны быть
чистыми (pure) — они не должны мутировать переданный df.
Все файлы app/**/*.py проверяются на:
  1. Прямые мутации через индексирование: df['col'] = value
  2. Мутации через .loc/.iloc/.at/.iat: df.loc[0, 'col'] = value
  3. Аугментированные присваивания (имя): df['col'] += value
  4. Аугментированные присваивания (атрибут): df.loc[0] += value  ← FIX: было не задетектировано
  5. Использование inplace=True на DataFrame-методах
  6. Алиасные присваивания без .copy(): df2 = df (потенциальный side-effect)

Чистые функции определены в PURE_FUNCTION_FILES — здесь запрещены любые мутации.
В остальных файлах app/**/*.py запрещены inplace=True и алиасные мутации.
Исключение: app/core/cleaner.py — имеет право строить df_clean из df_raw через subscript.

KNOWN LIMITATION: алиас-цепочки (df2 = df; df2['col'] = val) не отслеживаются —
для этого нужен полноценный data flow анализ, выходящий за рамки статического AST-обхода.
"""

import ast
import os
import sys
import textwrap
from pathlib import Path
from typing import List

import pytest

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------

# Корень проекта — директория, содержащая папку app/
PROJECT_ROOT = Path(__file__).parent.parent

# Папка с исходным кодом приложения (Section 4 — Project File Structure)
APP_DIR = PROJECT_ROOT / "app"

# Файлы с чистыми функциями — мутации ПОЛНОСТЬЮ запрещены (Section 9, Section 6)
# Metric-функции принимают df и обязаны возвращать новое значение, не меняя входной df
PURE_FUNCTION_FILES: List[str] = [
    "core/metrics.py",
    "core/forecast.py",
    "core/simulation.py",
]

# Файл, которому разрешены subscript-мутации при построении df_clean (Section 3, Section 4)
# clean_data() создаёт df_clean — это намеренно
CLEANER_FILE = os.path.join("core", "cleaner.py")

# Имена переменных, которые трактуются как DataFrame
# Любое имя, начинающееся с 'df', считается датафреймом
DF_NAME_PREFIX = "df"

# Методы-атрибуты DataFrame, через которые возможны subscript-мутации
MUTABLE_ATTRS = ("loc", "iloc", "at", "iat")

# Примечание: visit_Call флагирует ВСЕ вызовы inplace=True на df-* переменных —
# без фильтрации по конкретному списку методов. Это намеренно: спека (Section 17)
# запрещает inplace-мутации полностью, независимо от имени метода.


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _is_df_name(name: str) -> bool:
    """Возвращает True, если имя переменной выглядит как DataFrame.
    Spec Section 14: ключевые переменные df_clean, df_raw, df_filtered и т.д."""
    return name.startswith(DF_NAME_PREFIX)


def _collect_app_files() -> List[Path]:
    """Собирает все .py файлы из app/**/*.py.
    Spec Section 17: «across app/**/*.py»."""
    if not APP_DIR.exists():
        return []
    return sorted(APP_DIR.rglob("*.py"))


def _relative(path: Path) -> str:
    """Возвращает путь относительно APP_DIR для удобства вывода."""
    try:
        return str(path.relative_to(APP_DIR))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# AST NodeVisitor
# ---------------------------------------------------------------------------

class MutationViolation:
    """Описание одного нарушения иммутабельности."""

    def __init__(self, violation_type: str, file_path: str, line: int, detail: str):
        self.violation_type = violation_type
        self.file_path = file_path
        self.line = line
        self.detail = detail

    def __repr__(self) -> str:
        return (
            f"[{self.violation_type}] {self.file_path}:{self.line} — {self.detail}"
        )


class DataFrameMutationVisitor(ast.NodeVisitor):
    """
    AST NodeVisitor для обнаружения прямых и алиасных мутаций DataFrame.
    Spec Section 17: «AST NodeVisitor — direct + aliased mutations».

    Проверяет пять классов нарушений:
      A) direct_subscript      — df['col'] = value
      B) direct_subscript_attr — df.loc[...] = value / df.at[...] = value
      C) augmented_assign      — df['col'] += value  ИЛИ  df.loc[0] += value
      D) inplace_true          — df.dropna(inplace=True)
      E) aliased_no_copy       — df2 = df  (алиас без .copy())

    KNOWN LIMITATION: алиас-цепочки (df2 = df; df2['col'] = val) не отслеживаются —
    требует data flow анализа. Для статического AST-обхода это выходит за рамки задачи.
    """

    def __init__(self, filename: str, allow_subscript: bool = False):
        """
        :param filename: путь к файлу (для сообщений об ошибках)
        :param allow_subscript: если True — subscript-мутации разрешены (только cleaner.py)
        """
        self.filename = filename
        self.allow_subscript = allow_subscript
        self.violations: List[MutationViolation] = []

    # ------------------------------------------------------------------
    # Вспомогательный метод: добавить нарушение
    # ------------------------------------------------------------------

    def _add(self, vtype: str, line: int, detail: str) -> None:
        """Добавляет нарушение в список."""
        self.violations.append(MutationViolation(
            violation_type=vtype,
            file_path=self.filename,
            line=line,
            detail=detail,
        ))

    # ------------------------------------------------------------------
    # A + B + E: Обычные присваивания
    # ------------------------------------------------------------------

    def visit_Assign(self, node: ast.Assign) -> None:
        """
        Обрабатывает присваивания трёх видов:
          E) алиасное: df2 = df  (без .copy())
          A) прямое subscript: df['col'] = value
          B) через атрибут: df.loc[...] = value / df.at[...] = value
        """
        for target in node.targets:

            # --- A + B: subscript-мутации ---
            if isinstance(target, ast.Subscript) and not self.allow_subscript:
                obj = target.value

                # A: df['col'] = value — прямой subscript
                if isinstance(obj, ast.Name) and _is_df_name(obj.id):
                    self._add(
                        "direct_subscript",
                        node.lineno,
                        f"Прямая мутация через индексирование: {obj.id}[...] = ... "
                        f"(строка {node.lineno}). Используйте df.assign(...).",
                    )

                # B: df.loc[...] = value / df.iloc[...] = value / df.at[...] / df.iat[...]
                elif (
                    isinstance(obj, ast.Attribute)
                    and isinstance(obj.value, ast.Name)
                    and _is_df_name(obj.value.id)
                    and obj.attr in MUTABLE_ATTRS
                ):
                    self._add(
                        "direct_subscript_attr",
                        node.lineno,
                        f"Мутация через .{obj.attr}[...] = ...: {obj.value.id}.{obj.attr} "
                        f"(строка {node.lineno}). Используйте df.assign(...).",
                    )

            # --- E: алиасное присваивание без .copy() ---
            if isinstance(target, ast.Name) and _is_df_name(target.id):
                rhs = node.value
                # df2 = df — простой алиас (RHS — голое имя, начинающееся с 'df')
                if isinstance(rhs, ast.Name) and _is_df_name(rhs.id):
                    self._add(
                        "aliased_no_copy",
                        node.lineno,
                        f"Алиасное присваивание без .copy(): {target.id} = {rhs.id} "
                        f"(строка {node.lineno}). Используйте {target.id} = {rhs.id}.copy().",
                    )

        self.generic_visit(node)

    # ------------------------------------------------------------------
    # C: Аугментированные присваивания
    # ------------------------------------------------------------------

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        """
        C) Аугментированные присваивания через subscript.
        Два подвида:
          C1) df['col'] += value     — target.value — ast.Name
          C2) df.loc[0] += value     — target.value — ast.Attribute  ← ИСПРАВЛЕНО
              df.iloc[0, 1] += value
              df.at[0, 'col'] += value
              df.iat[0, 1] += value
        В отличие от Assign, аугментированное присваивание — ВСЕГДА мутация.
        allow_subscript не применяется: += запрещён даже в cleaner.py.
        """
        target = node.target
        if not isinstance(target, ast.Subscript):
            self.generic_visit(node)
            return

        obj = target.value

        # C1: df['col'] += value
        if isinstance(obj, ast.Name) and _is_df_name(obj.id):
            self._add(
                "augmented_assign",
                node.lineno,
                f"Аугментированное присваивание-мутация: {obj.id}[...] += ... "
                f"(строка {node.lineno}). Используйте df.assign(...).",
            )

        # C2: df.loc[0] += value / df.at[0, 'col'] += value (ранее не детектировалось!)
        elif (
            isinstance(obj, ast.Attribute)
            and isinstance(obj.value, ast.Name)
            and _is_df_name(obj.value.id)
            and obj.attr in MUTABLE_ATTRS
        ):
            self._add(
                "augmented_assign_attr",
                node.lineno,
                f"Аугментированное присваивание через .{obj.attr}: "
                f"{obj.value.id}.{obj.attr}[...] += ... (строка {node.lineno}). "
                f"Используйте df.assign(...).",
            )

        self.generic_visit(node)

    # ------------------------------------------------------------------
    # D: inplace=True
    # ------------------------------------------------------------------

    def visit_Call(self, node: ast.Call) -> None:
        """
        D) df.dropna(inplace=True) — мутирует объект на месте.
        Spec Section 9: функции-метрики обязаны быть чистыми.
        """
        for keyword in node.keywords:
            # Ищем inplace=True
            if (
                keyword.arg == "inplace"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
            ):
                # Убеждаемся, что вызов происходит на df-переменной
                if isinstance(node.func, ast.Attribute):
                    caller = node.func.value
                    method_name = node.func.attr
                    if isinstance(caller, ast.Name) and _is_df_name(caller.id):
                        self._add(
                            "inplace_true",
                            node.lineno,
                            f"inplace=True на {caller.id}.{method_name}() "
                            f"(строка {node.lineno}). "
                            f"Используйте {caller.id} = {caller.id}.{method_name}(...).",
                        )
        self.generic_visit(node)


# ---------------------------------------------------------------------------
# Функция анализа одного файла
# ---------------------------------------------------------------------------

def _analyse_file(
    file_path: Path,
    allow_subscript: bool = False,
) -> List[MutationViolation]:
    """
    Разбирает файл через ast.parse() и запускает DataFrameMutationVisitor.
    Возвращает список нарушений.

    :param file_path: абсолютный путь к .py файлу
    :param allow_subscript: разрешить subscript-мутации (только для cleaner.py)
    """
    try:
        source = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        # Не можем прочитать файл — считаем это предупреждением, не ошибкой
        pytest.skip(f"Не удалось прочитать {file_path}: {exc}")
        return []

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as exc:
        pytest.fail(
            f"SyntaxError при разборе {file_path}: {exc}. "
            f"Файл должен быть валидным Python (Spec Section 16, Step 8)."
        )
        return []

    visitor = DataFrameMutationVisitor(
        filename=_relative(file_path),
        allow_subscript=allow_subscript,
    )
    visitor.visit(tree)
    return visitor.violations


# ---------------------------------------------------------------------------
# Тесты: чистые функции (metrics.py, forecast.py, simulation.py)
# ---------------------------------------------------------------------------

class TestImmutabilityPureFunctions:
    """
    Группа тестов для PURE_FUNCTION_FILES (metrics.py, forecast.py, simulation.py).
    Spec Section 9: функции чистые — принимают df, не изменяют его.
    Spec Section 17: AST NodeVisitor — direct + aliased mutations.

    В этих файлах ЗАПРЕЩЕНЫ любые мутации DataFrame.
    """

    @pytest.mark.parametrize("relative_path", PURE_FUNCTION_FILES)
    def test_no_direct_subscript_mutation(self, relative_path: str) -> None:
        """
        Проверяет: df['col'] = value не встречается в чистых функциях.
        Spec Section 9: calculate_mrr(df) возвращает float, df не изменяется.
        """
        file_path = APP_DIR / relative_path
        if not file_path.exists():
            pytest.skip(f"Файл ещё не создан: {relative_path} (Spec Section 16 Step 8)")

        violations = _analyse_file(file_path, allow_subscript=False)
        subscript_v = [
            v for v in violations
            if v.violation_type in ("direct_subscript", "direct_subscript_attr")
        ]
        assert not subscript_v, (
            f"\n[{relative_path}] Прямые subscript-мутации (Spec Section 9):\n"
            + "\n".join(f"  • {v}" for v in subscript_v)
        )

    @pytest.mark.parametrize("relative_path", PURE_FUNCTION_FILES)
    def test_no_inplace_true(self, relative_path: str) -> None:
        """
        Проверяет: inplace=True отсутствует в чистых функциях.
        Spec Section 9.
        """
        file_path = APP_DIR / relative_path
        if not file_path.exists():
            pytest.skip(f"Файл ещё не создан: {relative_path} (Spec Section 16 Step 8)")

        violations = _analyse_file(file_path, allow_subscript=False)
        inplace_v = [v for v in violations if v.violation_type == "inplace_true"]
        assert not inplace_v, (
            f"\n[{relative_path}] inplace=True в чистой функции (Spec Section 9):\n"
            + "\n".join(f"  • {v}" for v in inplace_v)
        )

    @pytest.mark.parametrize("relative_path", PURE_FUNCTION_FILES)
    def test_no_aliased_mutation_without_copy(self, relative_path: str) -> None:
        """
        Проверяет: алиасные присваивания (df2 = df) отсутствуют без .copy().
        Spec Section 17: aliased mutations.
        """
        file_path = APP_DIR / relative_path
        if not file_path.exists():
            pytest.skip(f"Файл ещё не создан: {relative_path} (Spec Section 16 Step 8)")

        violations = _analyse_file(file_path, allow_subscript=False)
        alias_v = [v for v in violations if v.violation_type == "aliased_no_copy"]
        assert not alias_v, (
            f"\n[{relative_path}] Алиасные мутации без .copy() (Spec Section 17):\n"
            + "\n".join(f"  • {v}" for v in alias_v)
        )

    @pytest.mark.parametrize("relative_path", PURE_FUNCTION_FILES)
    def test_no_augmented_assign_mutation(self, relative_path: str) -> None:
        """
        Проверяет: df['col'] += value и df.loc[0] += value отсутствуют.
        Spec Section 17: direct mutations. Покрывает оба подвида (C1 и C2).
        """
        file_path = APP_DIR / relative_path
        if not file_path.exists():
            pytest.skip(f"Файл ещё не создан: {relative_path} (Spec Section 16 Step 8)")

        violations = _analyse_file(file_path, allow_subscript=False)
        aug_v = [
            v for v in violations
            if v.violation_type in ("augmented_assign", "augmented_assign_attr")
        ]
        assert not aug_v, (
            f"\n[{relative_path}] Аугментированные мутации DataFrame (Spec Section 17):\n"
            + "\n".join(f"  • {v}" for v in aug_v)
        )


# ---------------------------------------------------------------------------
# Тесты: все файлы app/**/*.py
# ---------------------------------------------------------------------------

class TestImmutabilityAllAppFiles:
    """
    Группа тестов для ВСЕХ файлов app/**/*.py.
    Spec Section 17: «across app/**/*.py».

    inplace=True и алиасные мутации запрещены глобально.
    Subscript-мутации разрешены только в cleaner.py.
    """

    def test_no_inplace_true_anywhere(self) -> None:
        """
        Проверяет: inplace=True нигде не используется в app/**/*.py.
        Spec Section 17.
        """
        app_files = _collect_app_files()
        if not app_files:
            pytest.skip(f"Папка {APP_DIR} не найдена или пуста (Spec Section 16 Step 8)")

        all_v: List[MutationViolation] = []
        for fp in app_files:
            vs = _analyse_file(fp, allow_subscript=True)
            all_v.extend(v for v in vs if v.violation_type == "inplace_true")

        assert not all_v, (
            f"\n[ALL app/**/*.py] inplace=True запрещён (Spec Section 17):\n"
            + "\n".join(f"  • {v}" for v in all_v)
        )

    def test_no_aliased_mutation_anywhere(self) -> None:
        """
        Проверяет: алиасные присваивания DataFrame без .copy() отсутствуют везде.
        Spec Section 17: aliased mutations across app/**/*.py.
        """
        app_files = _collect_app_files()
        if not app_files:
            pytest.skip(f"Папка {APP_DIR} не найдена или пуста (Spec Section 16 Step 8)")

        all_v: List[MutationViolation] = []
        for fp in app_files:
            vs = _analyse_file(fp, allow_subscript=True)
            all_v.extend(v for v in vs if v.violation_type == "aliased_no_copy")

        assert not all_v, (
            f"\n[ALL app/**/*.py] Алиасные мутации без .copy() (Spec Section 17):\n"
            + "\n".join(f"  • {v}" for v in all_v)
        )

    def test_non_cleaner_files_have_no_subscript_mutations(self) -> None:
        """
        Проверяет: subscript-мутации отсутствуют во всех файлах КРОМЕ cleaner.py.
        Spec Section 9, Section 17. cleaner.py — единственное исключение (Section 4).
        """
        app_files = _collect_app_files()
        if not app_files:
            pytest.skip("Нет файлов для проверки")

        non_cleaner = [f for f in app_files if _relative(f) != CLEANER_FILE]
        all_v: List[MutationViolation] = []
        for fp in non_cleaner:
            vs = _analyse_file(fp, allow_subscript=False)
            all_v.extend(
                v for v in vs
                if v.violation_type in ("direct_subscript", "direct_subscript_attr")
            )

        assert not all_v, (
            f"\n[ALL except cleaner.py] Subscript-мутации запрещены (Spec Section 17):\n"
            + "\n".join(f"  • {v}" for v in all_v)
        )

    def test_augmented_assign_mutation_nowhere(self) -> None:
        """
        Проверяет: df['col'] += value и df.loc[...] += value нигде не встречаются.
        Spec Section 17: direct mutations. Оба подвида (C1 и C2) запрещены глобально,
        включая cleaner.py — += всегда мутация, не может быть «функциональным».
        """
        app_files = _collect_app_files()
        if not app_files:
            pytest.skip("Нет файлов для проверки")

        all_v: List[MutationViolation] = []
        for fp in app_files:
            # allow_subscript=False: += не разрешён нигде, даже в cleaner.py
            vs = _analyse_file(fp, allow_subscript=False)
            all_v.extend(
                v for v in vs
                if v.violation_type in ("augmented_assign", "augmented_assign_attr")
            )

        assert not all_v, (
            f"\n[ALL app/**/*.py] Аугментированные subscript-мутации (Spec Section 17):\n"
            + "\n".join(f"  • {v}" for v in all_v)
        )

    def test_cleaner_subscript_mutations_are_permitted(self) -> None:
        """
        Проверяет, что cleaner.py МОЖЕТ содержать subscript-мутации без флага нарушения.
        Spec Section 4: clean_data() строит df_clean из df_raw — это допустимо.
        Позитивный тест: убеждаемся что allow_subscript=True снимает флаги для cleaner.py.

        Примечание: тест проходит (skip), если cleaner.py ещё не создан.
        Тест проходит (pass), если в cleaner.py нет subscript-мутаций — это тоже OK.
        Тест ПАДАЕТ только если cleaner.py содержит inplace=True или алиасы без copy().
        """
        cleaner_path = APP_DIR / CLEANER_FILE
        if not cleaner_path.exists():
            pytest.skip("cleaner.py не создан (Spec Section 16 Step 3)")

        # allow_subscript=True — разрешаем subscript-мутации
        violations = _analyse_file(cleaner_path, allow_subscript=True)
        # Даже в cleaner.py запрещены inplace и алиасы
        bad = [
            v for v in violations
            if v.violation_type in (
                "inplace_true", "aliased_no_copy",
                "augmented_assign", "augmented_assign_attr",
            )
        ]
        assert not bad, (
            f"\n[cleaner.py] inplace=True, алиасы без copy() и += запрещены даже в cleaner.py "
            f"(Spec Section 17):\n"
            + "\n".join(f"  • {v}" for v in bad)
        )

        # Позитивная проверка: subscript-флаги НЕ генерируются для cleaner.py
        subscript_v = [
            v for v in violations
            if v.violation_type in ("direct_subscript", "direct_subscript_attr")
        ]
        assert not subscript_v, (
            f"\n[cleaner.py] Subscript-мутации неожиданно флагированы при allow_subscript=True "
            f"— ошибка в детекторе:\n"
            + "\n".join(f"  • {v}" for v in subscript_v)
        )


# ---------------------------------------------------------------------------
# Тесты: валидность Python-кода
# ---------------------------------------------------------------------------

class TestImmutabilityASTParseable:
    """
    Вспомогательная группа: все файлы app/**/*.py должны быть валидным Python.
    Spec Section 16, Step 8: «Full test suite — all tests pass before deploy».
    """

    def test_all_app_files_are_valid_python(self) -> None:
        """
        Проверяет, что все app/**/*.py парсятся без SyntaxError.
        Базовая гарантия перед AST-анализом мутаций.
        """
        app_files = _collect_app_files()
        if not app_files:
            pytest.skip(f"Папка {APP_DIR} пуста или не существует")

        errors: List[str] = []
        for fp in app_files:
            try:
                source = fp.read_text(encoding="utf-8")
                ast.parse(source, filename=str(fp))
            except SyntaxError as exc:
                errors.append(f"{_relative(fp)}: {exc}")
            except (OSError, UnicodeDecodeError) as exc:
                errors.append(f"{_relative(fp)}: read error — {exc}")

        assert not errors, (
            f"\n[app/**/*.py] SyntaxError (Spec Section 16 Step 8):\n"
            + "\n".join(f"  • {e}" for e in errors)
        )

    def test_app_directory_exists(self) -> None:
        """
        Проверяет, что директория app/ существует.
        Spec Section 4 — Project File Structure, Section 16 Step 8.
        """
        assert APP_DIR.exists(), (
            f"Директория {APP_DIR} не найдена. "
            f"Убедитесь, что Steps 1–7 из Section 16 выполнены."
        )
        assert APP_DIR.is_dir(), f"{APP_DIR} должна быть директорией."

    def test_pure_function_files_exist(self) -> None:
        """
        Проверяет, что все чистые функции-модули созданы к Step 8.
        Spec Section 16 Step 4: core/metrics.py + core/forecast.py + core/simulation.py.
        """
        missing = [rp for rp in PURE_FUNCTION_FILES if not (APP_DIR / rp).exists()]
        assert not missing, (
            f"Файлы чистых функций не найдены (Spec Section 16 Step 4 → Step 8):\n"
            + "\n".join(f"  • app/{rp}" for rp in missing)
        )


# ---------------------------------------------------------------------------
# Юнит-тесты самого AST NodeVisitor (тестируем тест-инфраструктуру)
# ---------------------------------------------------------------------------

class TestMutationVisitorUnit:
    """
    Тестируем DataFrameMutationVisitor на синтетическом коде.
    Гарантирует корректность детектора до запуска по реальным файлам.
    """

    def _visit(self, source: str, allow_subscript: bool = False) -> List[MutationViolation]:
        """Парсит строку кода и возвращает список нарушений."""
        tree = ast.parse(textwrap.dedent(source))
        visitor = DataFrameMutationVisitor(filename="<test>", allow_subscript=allow_subscript)
        visitor.visit(tree)
        return visitor.violations

    def _types(self, source: str, allow_subscript: bool = False) -> List[str]:
        """Возвращает только типы нарушений."""
        return [v.violation_type for v in self._visit(source, allow_subscript)]

    # --- A: прямые subscript-мутации ---

    def test_direct_subscript_detected(self) -> None:
        """Детектирует df['col'] = value."""
        assert "direct_subscript" in self._types("df_clean['col'] = 1")

    def test_direct_subscript_allowed_in_cleaner(self) -> None:
        """В cleaner.py subscript-мутации разрешены — нарушений нет."""
        v = [x for x in self._visit("df_clean['col'] = 1", allow_subscript=True)
             if x.violation_type == "direct_subscript"]
        assert not v

    # --- B: мутации через .loc/.iloc/.at/.iat ---

    def test_loc_mutation_detected(self) -> None:
        """Детектирует df.loc[0, 'col'] = 99."""
        assert "direct_subscript_attr" in self._types("df_clean.loc[0, 'col'] = 99")

    def test_iloc_mutation_detected(self) -> None:
        """Детектирует df.iloc[0] = 0."""
        assert "direct_subscript_attr" in self._types("df.iloc[0] = 0")

    def test_at_mutation_detected(self) -> None:
        """Детектирует df.at[0, 'col'] = 5."""
        assert "direct_subscript_attr" in self._types("df_clean.at[0, 'col'] = 5")

    def test_iat_mutation_detected(self) -> None:
        """Детектирует df.iat[0, 1] = 5."""
        assert "direct_subscript_attr" in self._types("df.iat[0, 1] = 5")

    def test_loc_mutation_allowed_in_cleaner(self) -> None:
        """В cleaner.py df.loc[...] = value тоже разрешён (allow_subscript=True)."""
        v = [x for x in self._visit("df_clean.loc[0, 'col'] = 1", allow_subscript=True)
             if x.violation_type == "direct_subscript_attr"]
        assert not v

    # --- C1: аугментированные присваивания через имя ---

    def test_augmented_assign_name_detected(self) -> None:
        """Детектирует df['amount'] += 100."""
        assert "augmented_assign" in self._types("df['amount'] += 100")

    def test_non_df_augmented_assign_ignored(self) -> None:
        """Аугментированное присваивание на не-df переменной игнорируется."""
        assert "augmented_assign" not in self._types("result['key'] += 1")

    # --- C2: аугментированные присваивания через атрибут (ранее не детектировалось) ---

    def test_augmented_assign_loc_detected(self) -> None:
        """Детектирует df_clean.loc[0] += 1 — ранее не ловилось (ИСПРАВЛЕНО)."""
        assert "augmented_assign_attr" in self._types("df_clean.loc[0] += 1")

    def test_augmented_assign_iloc_detected(self) -> None:
        """Детектирует df.iloc[0, 1] += 5."""
        assert "augmented_assign_attr" in self._types("df.iloc[0, 1] += 5")

    def test_augmented_assign_at_detected(self) -> None:
        """Детектирует df.at[0, 'col'] += 2."""
        assert "augmented_assign_attr" in self._types("df.at[0, 'col'] += 2")

    def test_augmented_assign_iat_detected(self) -> None:
        """Детектирует df.iat[0, 1] += 2."""
        assert "augmented_assign_attr" in self._types("df.iat[0, 1] += 2")

    def test_augmented_assign_attr_non_df_ignored(self) -> None:
        """df.loc на не-df переменной игнорируется."""
        assert "augmented_assign_attr" not in self._types("result.loc[0] += 1")

    # --- D: inplace=True ---

    def test_inplace_true_detected(self) -> None:
        """Детектирует df.dropna(inplace=True)."""
        assert "inplace_true" in self._types("df_clean.dropna(inplace=True)")

    def test_inplace_false_not_flagged(self) -> None:
        """df.dropna(inplace=False) — не мутация."""
        v = [x for x in self._visit("df_clean.dropna(inplace=False)")
             if x.violation_type == "inplace_true"]
        assert not v

    def test_inplace_on_non_df_ignored(self) -> None:
        """inplace=True на не-df переменной игнорируется."""
        v = [x for x in self._visit("result.dropna(inplace=True)")
             if x.violation_type == "inplace_true"]
        assert not v

    # --- E: алиасные присваивания ---

    def test_alias_without_copy_detected(self) -> None:
        """Детектирует df_filtered = df_clean (без .copy())."""
        assert "aliased_no_copy" in self._types("df_filtered = df_clean")

    def test_alias_with_copy_not_detected(self) -> None:
        """df2 = df.copy() — корректно, нарушения нет."""
        v = [x for x in self._visit("df_filtered = df_clean.copy()")
             if x.violation_type == "aliased_no_copy"]
        assert not v

    def test_df_slice_not_flagged_as_alias(self) -> None:
        """df2 = df[df['col'] > 0] — фильтрация (RHS не голое имя), не алиас."""
        v = [x for x in self._visit("df_filtered = df_clean[df_clean['amount'] > 0]")
             if x.violation_type == "aliased_no_copy"]
        assert not v

    def test_df_assign_call_not_flagged_as_alias(self) -> None:
        """df2 = df.assign(col=1) — вызов метода, не алиас."""
        v = [x for x in self._visit("df_result = df_clean.assign(col=1)")
             if x.violation_type == "aliased_no_copy"]
        assert not v

    # --- Чистый код — нет нарушений ---

    def test_pure_metric_code_no_violations(self) -> None:
        """
        Типичный код метрической функции не вызывает нарушений.
        Spec Section 9: calculate_mrr(df) возвращает float, df не изменяется.
        """
        clean_code = """
        def calculate_mrr(df):
            active = df[
                (df['status'] == 'active') & (df['amount'] > 0)
            ]
            per_customer = active.groupby('customer_id')['amount'].sum()
            return float(per_customer.sum())
        """
        violations = self._visit(clean_code)
        assert not violations, (
            f"Ложные срабатывания на чистом коде метрики:\n"
            + "\n".join(str(v) for v in violations)
        )

    def test_clean_data_with_allow_subscript_no_violations(self) -> None:
        """
        Типичный код cleaner.py с allow_subscript=True не вызывает нарушений.
        Spec Section 4: clean_data() → df_clean + cleaning_report.
        """
        cleaner_code = """
        def clean_data(df_raw):
            df_clean = df_raw.copy()
            df_clean['status'] = df_clean['status'].str.lower()
            df_clean['amount'] = df_clean['amount'].fillna(0)
            return df_clean
        """
        violations = self._visit(cleaner_code, allow_subscript=True)
        # subscript-мутации разрешены в cleaner — только inplace/alias/augassign запрещены
        bad = [
            v for v in violations
            if v.violation_type in (
                "inplace_true", "aliased_no_copy",
                "augmented_assign", "augmented_assign_attr",
            )
        ]
        assert not bad, (
            f"Ложные срабатывания на коде cleaner.py:\n"
            + "\n".join(str(v) for v in bad)
        )

    def test_augmented_loc_detected_even_with_allow_subscript(self) -> None:
        """
        df.loc[0] += 1 детектируется ДАЖЕ с allow_subscript=True (cleaner.py).
        += — это всегда мутация, исключений нет (Spec Section 17).
        """
        v = [x for x in self._visit("df_clean.loc[0] += 1", allow_subscript=True)
             if x.violation_type == "augmented_assign_attr"]
        assert v, "augmented_assign_attr должен детектироваться даже при allow_subscript=True"


# ---------------------------------------------------------------------------
# Запуск напрямую (для отладки без pytest)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Быстрая проверка всех файлов app/**/*.py без pytest
    app_files = _collect_app_files()
    if not app_files:
        print(f"[SKIP] Директория {APP_DIR} не найдена или пуста.")
        sys.exit(0)

    total_violations = 0
    for fp in app_files:
        is_cleaner = _relative(fp) == CLEANER_FILE
        vs = _analyse_file(fp, allow_subscript=is_cleaner)
        if vs:
            for v in vs:
                print(f"VIOLATION: {v}")
                total_violations += 1

    if total_violations == 0:
        print(f"[OK] Проверено {len(app_files)} файлов — мутаций не обнаружено.")
    else:
        print(f"\n[FAIL] Найдено {total_violations} нарушений в {len(app_files)} файлах.")
        sys.exit(1)
