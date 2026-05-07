"""
test_immutability.py
Spec: Section 17 — «AST NodeVisitor — direct + aliased mutations across app/**/*.py»

Принцип: метрические функции (metrics.py, forecast.py, simulation.py) обязаны быть
чистыми (pure) — они не должны мутировать переданный df.
Все файлы app/**/*.py проверяются на:
  1. Прямые мутации через индексирование: df['col'] = value
  2. Аугментированные присваивания: df['col'] += value
  3. Использование inplace=True на DataFrame-методах
  4. Алиасные присваивания без .copy(): df2 = df (потенциальный side-effect)

Чистые функции определены в PURE_FUNCTION_FILES — здесь запрещены любые мутации.
В остальных файлах app/**/*.py запрещены inplace=True и алиасные мутации.
Исключение: app/core/cleaner.py — имеет право строить df_clean из df_raw.
"""

import ast
import os
import sys
import textwrap
from pathlib import Path
from typing import List, Dict, Any

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

    Проверяет три класса нарушений:
      A) direct_subscript   — df['col'] = value  /  df.loc[...] = value
      B) augmented_assign   — df['col'] += value
      C) inplace_true       — df.dropna(inplace=True)
      D) aliased_no_copy    — df2 = df  (алиас без .copy())
    """

    def __init__(self, filename: str, allow_subscript: bool = False):
        """
        :param filename: путь к файлу (для сообщений об ошибках)
        :param allow_subscript: если True — subscript-мутации разрешены (для cleaner.py)
        """
        self.filename = filename
        self.allow_subscript = allow_subscript
        self.violations: List[MutationViolation] = []

        # Словарь алиасов: {алиас: оригинал} — отслеживаем в рамках модуля
        self._aliases: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # A + D: Обычные присваивания
    # ------------------------------------------------------------------

    def visit_Assign(self, node: ast.Assign) -> None:
        """
        Обрабатывает присваивания двух видов:
          D) алиасное: df2 = df  (без .copy())
          A) прямое subscript: df['col'] = value
        """
        for target in node.targets:

            # --- A: прямая subscript-мутация ---
            if isinstance(target, ast.Subscript) and not self.allow_subscript:
                obj = target.value
                if isinstance(obj, ast.Name) and _is_df_name(obj.id):
                    self.violations.append(MutationViolation(
                        violation_type="direct_subscript",
                        file_path=self.filename,
                        line=node.lineno,
                        detail=(
                            f"Прямая мутация DataFrame через индексирование: "
                            f"{obj.id}[...] = ... "
                            f"(строка {node.lineno}). "
                            f"Используйте df = df.assign(...) или df.copy()."
                        ),
                    ))

                # Attr-доступ: df.loc[...] = value / df.iloc[...] = value
                if isinstance(obj, ast.Attribute) and isinstance(obj.value, ast.Name):
                    if _is_df_name(obj.value.id) and obj.attr in ("loc", "iloc", "at", "iat"):
                        self.violations.append(MutationViolation(
                            violation_type="direct_subscript_attr",
                            file_path=self.filename,
                            line=node.lineno,
                            detail=(
                                f"Мутация DataFrame через .{obj.attr}[...] = ...: "
                                f"{obj.value.id}.{obj.attr} (строка {node.lineno}). "
                                f"Используйте pd.DataFrame.assign() или copy()."
                            ),
                        ))

            # --- D: алиасное присваивание без .copy() ---
            if isinstance(target, ast.Name) and _is_df_name(target.id):
                rhs = node.value

                # df2 = df — простой алиас
                if isinstance(rhs, ast.Name) and _is_df_name(rhs.id):
                    self._aliases[target.id] = rhs.id
                    self.violations.append(MutationViolation(
                        violation_type="aliased_no_copy",
                        file_path=self.filename,
                        line=node.lineno,
                        detail=(
                            f"Алиасное присваивание без .copy(): "
                            f"{target.id} = {rhs.id} (строка {node.lineno}). "
                            f"Используйте {target.id} = {rhs.id}.copy()."
                        ),
                    ))

        self.generic_visit(node)

    # ------------------------------------------------------------------
    # B: Аугментированные присваивания
    # ------------------------------------------------------------------

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        """
        B) df['col'] += value — всегда мутация.
        Spec Section 17: прямые мутации.
        """
        target = node.target
        if isinstance(target, ast.Subscript):
            obj = target.value
            if isinstance(obj, ast.Name) and _is_df_name(obj.id):
                self.violations.append(MutationViolation(
                    violation_type="augmented_assign",
                    file_path=self.filename,
                    line=node.lineno,
                    detail=(
                        f"Аугментированное присваивание-мутация: "
                        f"{obj.id}[...] += ... (строка {node.lineno})."
                    ),
                ))
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # C: inplace=True
    # ------------------------------------------------------------------

    def visit_Call(self, node: ast.Call) -> None:
        """
        C) df.dropna(inplace=True) — мутирует объект на месте.
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
                        self.violations.append(MutationViolation(
                            violation_type="inplace_true",
                            file_path=self.filename,
                            line=node.lineno,
                            detail=(
                                f"inplace=True на {caller.id}.{method_name}() "
                                f"(строка {node.lineno}). "
                                f"Используйте {caller.id} = {caller.id}.{method_name}(...)."
                            ),
                        ))
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
# Тесты
# ---------------------------------------------------------------------------

class TestImmutabilityPureFunctions:
    """
    Группа тестов для PURE_FUNCTION_FILES (metrics.py, forecast.py, simulation.py).
    Spec Section 9: «Do NOT cache individual metric functions» — функции чистые.
    Spec Section 17: AST NodeVisitor — direct + aliased mutations.

    В этих файлах ЗАПРЕЩЕНЫ любые мутации DataFrame:
      - subscript-присваивания
      - inplace=True
      - алиасы без .copy()
    """

    @pytest.mark.parametrize("relative_path", PURE_FUNCTION_FILES)
    def test_no_direct_subscript_mutation(self, relative_path: str) -> None:
        """
        Проверяет: df['col'] = value не встречается в чистых функциях.
        Spec Section 9: метрические функции принимают (df) и возвращают скаляр/None.
        Прямая запись в df нарушает чистоту функции и может портить кеш st.cache_data.
        """
        file_path = APP_DIR / relative_path
        if not file_path.exists():
            pytest.skip(f"Файл ещё не создан: {relative_path} (Spec Section 16 Step 8)")

        violations = _analyse_file(file_path, allow_subscript=False)
        subscript_violations = [
            v for v in violations if v.violation_type in ("direct_subscript", "direct_subscript_attr")
        ]

        assert not subscript_violations, (
            f"\n[{relative_path}] Обнаружены прямые subscript-мутации DataFrame "
            f"(Spec Section 9 — pure functions):\n"
            + "\n".join(f"  • {v}" for v in subscript_violations)
        )

    @pytest.mark.parametrize("relative_path", PURE_FUNCTION_FILES)
    def test_no_inplace_true(self, relative_path: str) -> None:
        """
        Проверяет: inplace=True отсутствует в чистых функциях.
        Spec Section 9: функции не должны мутировать входной df.
        """
        file_path = APP_DIR / relative_path
        if not file_path.exists():
            pytest.skip(f"Файл ещё не создан: {relative_path} (Spec Section 16 Step 8)")

        violations = _analyse_file(file_path, allow_subscript=False)
        inplace_violations = [v for v in violations if v.violation_type == "inplace_true"]

        assert not inplace_violations, (
            f"\n[{relative_path}] Обнаружено inplace=True в чистой функции "
            f"(Spec Section 9):\n"
            + "\n".join(f"  • {v}" for v in inplace_violations)
        )

    @pytest.mark.parametrize("relative_path", PURE_FUNCTION_FILES)
    def test_no_aliased_mutation_without_copy(self, relative_path: str) -> None:
        """
        Проверяет: алиасные присваивания (df2 = df) отсутствуют без вызова .copy().
        Spec Section 17: «aliased mutations» — алиас без copy() изменяет оригинал.
        """
        file_path = APP_DIR / relative_path
        if not file_path.exists():
            pytest.skip(f"Файл ещё не создан: {relative_path} (Spec Section 16 Step 8)")

        violations = _analyse_file(file_path, allow_subscript=False)
        alias_violations = [v for v in violations if v.violation_type == "aliased_no_copy"]

        assert not alias_violations, (
            f"\n[{relative_path}] Алиасные мутации без .copy() "
            f"(Spec Section 17 — aliased mutations):\n"
            + "\n".join(f"  • {v}" for v in alias_violations)
        )

    @pytest.mark.parametrize("relative_path", PURE_FUNCTION_FILES)
    def test_no_augmented_assign_mutation(self, relative_path: str) -> None:
        """
        Проверяет: df['col'] += value не встречается в чистых функциях.
        Spec Section 17: direct mutations.
        """
        file_path = APP_DIR / relative_path
        if not file_path.exists():
            pytest.skip(f"Файл ещё не создан: {relative_path} (Spec Section 16 Step 8)")

        violations = _analyse_file(file_path, allow_subscript=False)
        aug_violations = [v for v in violations if v.violation_type == "augmented_assign"]

        assert not aug_violations, (
            f"\n[{relative_path}] Аугментированные мутации DataFrame "
            f"(Spec Section 17):\n"
            + "\n".join(f"  • {v}" for v in aug_violations)
        )


class TestImmutabilityAllAppFiles:
    """
    Группа тестов для ВСЕХ файлов app/**/*.py.
    Spec Section 17: «across app/**/*.py».

    inplace=True и алиасные мутации запрещены глобально.
    Исключение для subscript-мутаций: cleaner.py (строит df_clean из df_raw).
    """

    def test_no_inplace_true_anywhere(self) -> None:
        """
        Проверяет: inplace=True нигде не используется в app/**/*.py.
        Spec Section 17 — запрет inplace-мутаций по всему приложению.
        Всегда безопаснее: df = df.method() вместо df.method(inplace=True).
        """
        app_files = _collect_app_files()
        if not app_files:
            pytest.skip(f"Папка {APP_DIR} не найдена или пуста (Spec Section 16 Step 8)")

        all_violations: List[MutationViolation] = []
        for file_path in app_files:
            violations = _analyse_file(file_path, allow_subscript=True)
            inplace_v = [v for v in violations if v.violation_type == "inplace_true"]
            all_violations.extend(inplace_v)

        assert not all_violations, (
            f"\n[ALL app/**/*.py] inplace=True запрещён во всём приложении "
            f"(Spec Section 17):\n"
            + "\n".join(f"  • {v}" for v in all_violations)
        )

    def test_no_aliased_mutation_anywhere(self) -> None:
        """
        Проверяет: алиасные присваивания DataFrame без .copy() отсутствуют везде.
        Spec Section 17: «aliased mutations across app/**/*.py».
        df2 = df создаёт ссылку на тот же объект — любое последующее изменение
        df2 меняет df, что нарушает чистоту метрических функций (Section 9).
        """
        app_files = _collect_app_files()
        if not app_files:
            pytest.skip(f"Папка {APP_DIR} не найдена или пуста (Spec Section 16 Step 8)")

        all_violations: List[MutationViolation] = []
        for file_path in app_files:
            violations = _analyse_file(file_path, allow_subscript=True)
            alias_v = [v for v in violations if v.violation_type == "aliased_no_copy"]
            all_violations.extend(alias_v)

        assert not all_violations, (
            f"\n[ALL app/**/*.py] Алиасные мутации без .copy() (Spec Section 17):\n"
            + "\n".join(f"  • {v}" for v in all_violations)
        )

    def test_cleaner_is_excluded_from_subscript_check(self) -> None:
        """
        Проверяет, что cleaner.py корректно ИСКЛЮЧЁН из строгой subscript-проверки.
        Spec Section 3: clean_data() строит df_clean — subscript-присваивания допустимы.
        Spec Section 4: app/core/cleaner.py — clean_data() returns df_clean + cleaning_report.
        Тест гарантирует, что исключение задокументировано и не применяется к другим файлам.
        """
        cleaner_path = APP_DIR / CLEANER_FILE
        if not cleaner_path.exists():
            pytest.skip(f"Файл cleaner.py не создан (Spec Section 16 Step 3)")

        # allow_subscript=True — subscript-мутации разрешены в cleaner.py
        violations = _analyse_file(cleaner_path, allow_subscript=True)
        # Проверяем только inplace и алиасы — они запрещены даже в cleaner.py
        bad_violations = [
            v for v in violations
            if v.violation_type in ("inplace_true", "aliased_no_copy")
        ]

        assert not bad_violations, (
            f"\n[cleaner.py] Даже в cleaner.py запрещены inplace=True и алиасы без copy() "
            f"(Spec Section 17):\n"
            + "\n".join(f"  • {v}" for v in bad_violations)
        )

    def test_pure_files_excluded_from_subscript_globally(self) -> None:
        """
        Проверяет, что PURE_FUNCTION_FILES не получают исключение для subscript-мутаций.
        Все прочие файлы (кроме cleaner.py) также не должны иметь исключения.
        Spec Section 9, Section 17.
        """
        app_files = _collect_app_files()
        if not app_files:
            pytest.skip("Нет файлов для проверки")

        non_cleaner_files = [
            f for f in app_files
            if _relative(f) != CLEANER_FILE
        ]

        all_violations: List[MutationViolation] = []
        for file_path in non_cleaner_files:
            violations = _analyse_file(file_path, allow_subscript=False)
            subscript_v = [
                v for v in violations
                if v.violation_type in ("direct_subscript", "direct_subscript_attr")
            ]
            all_violations.extend(subscript_v)

        assert not all_violations, (
            f"\n[ALL except cleaner.py] Прямые subscript-мутации запрещены "
            f"вне cleaner.py (Spec Section 17):\n"
            + "\n".join(f"  • {v}" for v in all_violations)
        )

    def test_augmented_assign_mutation_nowhere(self) -> None:
        """
        Проверяет: df['col'] += value нигде не встречается в app/**/*.py.
        Spec Section 17: direct mutations. Аугментированное присваивание через subscript
        всегда является мутацией и не может быть «функциональным».
        """
        app_files = _collect_app_files()
        if not app_files:
            pytest.skip("Нет файлов для проверки")

        all_violations: List[MutationViolation] = []
        for file_path in app_files:
            violations = _analyse_file(file_path, allow_subscript=True)
            aug_v = [v for v in violations if v.violation_type == "augmented_assign"]
            all_violations.extend(aug_v)

        assert not all_violations, (
            f"\n[ALL app/**/*.py] Аугментированные subscript-мутации (Spec Section 17):\n"
            + "\n".join(f"  • {v}" for v in all_violations)
        )


class TestImmutabilityASTParseable:
    """
    Вспомогательная группа: все файлы app/**/*.py должны быть валидным Python.
    Spec Section 16, Step 8: «Full test suite — all tests pass before deploy».
    Если файл не парсится — тест-раннер сам не сможет их импортировать.
    """

    def test_all_app_files_are_valid_python(self) -> None:
        """
        Проверяет, что все app/**/*.py парсятся без SyntaxError.
        Базовая гарантия перед AST-анализом мутаций.
        """
        app_files = _collect_app_files()
        if not app_files:
            pytest.skip(f"Папка {APP_DIR} пуста или не существует")

        syntax_errors: List[str] = []
        for file_path in app_files:
            try:
                source = file_path.read_text(encoding="utf-8")
                ast.parse(source, filename=str(file_path))
            except SyntaxError as exc:
                syntax_errors.append(f"{_relative(file_path)}: {exc}")
            except (OSError, UnicodeDecodeError) as exc:
                syntax_errors.append(f"{_relative(file_path)}: read error — {exc}")

        assert not syntax_errors, (
            f"\n[app/**/*.py] SyntaxError — файлы не могут быть проанализированы "
            f"(Spec Section 16 Step 8):\n"
            + "\n".join(f"  • {e}" for e in syntax_errors)
        )

    def test_app_directory_exists(self) -> None:
        """
        Проверяет, что директория app/ существует (Step 8 предполагает, что весь код уже написан).
        Spec Section 4 — Project File Structure, Section 16 Step 8.
        """
        assert APP_DIR.exists(), (
            f"Директория {APP_DIR} не найдена. "
            f"Убедитесь, что Steps 1–7 из Section 16 выполнены перед запуском теста."
        )
        assert APP_DIR.is_dir(), f"{APP_DIR} должна быть директорией."

    def test_pure_function_files_exist(self) -> None:
        """
        Проверяет, что все чистые функции-модули из Section 9 уже созданы к Step 8.
        Spec Section 16 Step 4: core/metrics.py + core/forecast.py + core/simulation.py.
        """
        missing = [
            rp for rp in PURE_FUNCTION_FILES
            if not (APP_DIR / rp).exists()
        ]
        assert not missing, (
            f"Следующие файлы чистых функций не найдены (Spec Section 16 Step 4 → Step 8):\n"
            + "\n".join(f"  • app/{rp}" for rp in missing)
        )


# ---------------------------------------------------------------------------
# Юнит-тесты самого AST NodeVisitor (тестируем тест-инфраструктуру)
# ---------------------------------------------------------------------------

class TestMutationVisitorUnit:
    """
    Тестируем сам MutationViolationVisitor на синтетическом коде.
    Это гарантирует корректность детектора мутаций до запуска по реальным файлам.
    """

    def _parse_and_visit(self, source: str, allow_subscript: bool = False) -> List[MutationViolation]:
        """Вспомогательный метод: парсит строку кода и возвращает список нарушений."""
        tree = ast.parse(textwrap.dedent(source))
        visitor = DataFrameMutationVisitor(filename="<test>", allow_subscript=allow_subscript)
        visitor.visit(tree)
        return visitor.violations

    # --- Прямые subscript-мутации ---

    def test_direct_subscript_detected(self) -> None:
        """Детектор находит df['col'] = value."""
        violations = self._parse_and_visit("df_clean['col'] = 1")
        types = [v.violation_type for v in violations]
        assert "direct_subscript" in types

    def test_direct_subscript_allowed_in_cleaner(self) -> None:
        """В cleaner.py subscript-мутации разрешены — нарушений нет."""
        violations = self._parse_and_visit("df_clean['col'] = 1", allow_subscript=True)
        subscript_v = [v for v in violations if v.violation_type == "direct_subscript"]
        assert not subscript_v

    def test_loc_mutation_detected(self) -> None:
        """Детектор находит df.loc[...] = value."""
        violations = self._parse_and_visit("df_clean.loc[0, 'col'] = 99")
        types = [v.violation_type for v in violations]
        assert "direct_subscript_attr" in types

    def test_iloc_mutation_detected(self) -> None:
        """Детектор находит df.iloc[...] = value."""
        violations = self._parse_and_visit("df.iloc[0] = 0")
        types = [v.violation_type for v in violations]
        assert "direct_subscript_attr" in types

    # --- Аугментированные присваивания ---

    def test_augmented_assign_detected(self) -> None:
        """Детектор находит df['col'] += 1."""
        violations = self._parse_and_visit("df['amount'] += 100")
        types = [v.violation_type for v in violations]
        assert "augmented_assign" in types

    def test_non_df_augmented_assign_ignored(self) -> None:
        """Аугментированное присваивание на не-df переменной игнорируется."""
        violations = self._parse_and_visit("result['key'] += 1")
        types = [v.violation_type for v in violations]
        assert "augmented_assign" not in types

    # --- inplace=True ---

    def test_inplace_true_detected(self) -> None:
        """Детектор находит df.dropna(inplace=True)."""
        violations = self._parse_and_visit("df_clean.dropna(inplace=True)")
        types = [v.violation_type for v in violations]
        assert "inplace_true" in types

    def test_inplace_false_not_flagged(self) -> None:
        """df.dropna(inplace=False) — не мутация, детектор не срабатывает."""
        violations = self._parse_and_visit("df_clean.dropna(inplace=False)")
        inplace_v = [v for v in violations if v.violation_type == "inplace_true"]
        assert not inplace_v

    def test_inplace_on_non_df_ignored(self) -> None:
        """inplace=True на не-df переменной игнорируется."""
        violations = self._parse_and_visit("result.dropna(inplace=True)")
        inplace_v = [v for v in violations if v.violation_type == "inplace_true"]
        assert not inplace_v

    # --- Алиасные присваивания ---

    def test_alias_without_copy_detected(self) -> None:
        """Детектор находит df2 = df (без .copy())."""
        violations = self._parse_and_visit("df_filtered = df_clean")
        types = [v.violation_type for v in violations]
        assert "aliased_no_copy" in types

    def test_alias_with_copy_not_detected(self) -> None:
        """df2 = df.copy() — корректно, нарушения нет."""
        violations = self._parse_and_visit("df_filtered = df_clean.copy()")
        alias_v = [v for v in violations if v.violation_type == "aliased_no_copy"]
        assert not alias_v

    def test_df_slice_not_flagged_as_alias(self) -> None:
        """df2 = df[df['col'] > 0] — фильтрация, не алиас."""
        violations = self._parse_and_visit(
            "df_filtered = df_clean[df_clean['amount'] > 0]"
        )
        alias_v = [v for v in violations if v.violation_type == "aliased_no_copy"]
        assert not alias_v

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
        violations = self._parse_and_visit(clean_code)
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
        # allow_subscript=True — как для cleaner.py
        violations = self._parse_and_visit(cleaner_code, allow_subscript=True)
        # Только inplace и алиасы могут остаться нарушениями
        bad = [
            v for v in violations
            if v.violation_type in ("inplace_true", "aliased_no_copy", "augmented_assign")
        ]
        assert not bad, (
            f"Ложные срабатывания на коде cleaner.py:\n"
            + "\n".join(str(v) for v in bad)
        )


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
