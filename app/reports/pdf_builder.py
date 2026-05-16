"""
reports/pdf_builder.py
SubAudit — Master Specification Sheet v2.9
Development Order Step 5 (Section 16)

Ответственность файла (Section 4):
  - generate_pdf() → bytes
  - Forecast gate (Section 10)
  - display_name + filename_safe_name из company_name (Section 14)
  - Watermark-логика по плану (Section 2)

Автор: строго по спецификации v2.9, никаких отступлений.
"""

from __future__ import annotations

import io
import math
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.pdfgen import canvas

# ---------------------------------------------------------------------------
# Константы (Section 2 — планы и правила PDF экспорта)
# ---------------------------------------------------------------------------

# Допустимые значения плана (Section 12 / Section 14)
_PLAN_FREE = "free"
_PLAN_STARTER = "starter"
_PLAN_PRO = "pro"

# Текст подложки для FREE-плана (Section 2 — "With watermark")
_WATERMARK_TEXT = "SubAudit FREE"

# Нижний колонтитул при заблокированном прогнозе (Section 10 — export gate)
_FORECAST_OMITTED_FOOTER = (
    "Forecast omitted — fewer than 6 months of data available."
)

# Предупреждение о пересчёте NRR (Section 6)
_NRR_WARNING_THRESHOLD = 200.0

# ---------------------------------------------------------------------------
# Цветовая палитра
# ---------------------------------------------------------------------------

_COLOR_PRIMARY = colors.HexColor("#1A56DB")      # синий заголовок
_COLOR_SECONDARY = colors.HexColor("#374151")    # тёмно-серый текст
_COLOR_ACCENT = colors.HexColor("#10B981")       # зелёный (позитив)
_COLOR_WARN = colors.HexColor("#F59E0B")         # оранжевый (предупреждение)
_COLOR_DANGER = colors.HexColor("#EF4444")       # красный (негатив)
_COLOR_LIGHT_BG = colors.HexColor("#F9FAFB")     # светлый фон блоков
_COLOR_BORDER = colors.HexColor("#E5E7EB")       # граница таблиц
_COLOR_WATERMARK = colors.Color(0.75, 0.75, 0.75, alpha=0.35)  # серая подложка

# ---------------------------------------------------------------------------
# Вспомогательные форматтеры
# ---------------------------------------------------------------------------


def _fmt_currency(value: float | None, currency: str = "USD") -> str:
    """Форматирует числовое значение в денежную строку."""
    if value is None:
        return "N/A"
    # Тысячные разделители, 2 знака после запятой
    return f"{currency} {value:,.2f}"


def _fmt_percent(value: float | None) -> str:
    """Форматирует значение как процент с 2 знаками."""
    if value is None:
        return "N/A"
    return f"{value:.2f}%"


def _fmt_int(value: int | None) -> str:
    """Форматирует целое число с разделителями тысяч."""
    if value is None:
        return "N/A"
    return f"{int(value):,}"


def _fmt_value(value: Any) -> str:
    """Универсальный форматтер для метрики неизвестного типа."""
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


# ---------------------------------------------------------------------------
# Построитель стилей
# ---------------------------------------------------------------------------


def _build_styles() -> dict[str, ParagraphStyle]:
    """
    Создаёт словарь именованных ParagraphStyle для всего документа.
    Вся типографика централизована здесь.
    """
    base = getSampleStyleSheet()

    styles: dict[str, ParagraphStyle] = {}

    # Заголовок документа (страница обложки)
    styles["doc_title"] = ParagraphStyle(
        "doc_title",
        parent=base["Title"],
        fontSize=26,
        textColor=_COLOR_PRIMARY,
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
    )

    # Подзаголовок обложки (название компании — только PRO, Section 2)
    styles["doc_subtitle"] = ParagraphStyle(
        "doc_subtitle",
        parent=base["Normal"],
        fontSize=14,
        textColor=_COLOR_SECONDARY,
        spaceAfter=4,
        alignment=TA_CENTER,
        fontName="Helvetica",
    )

    # Дата генерации
    styles["doc_date"] = ParagraphStyle(
        "doc_date",
        parent=base["Normal"],
        fontSize=10,
        textColor=colors.grey,
        spaceAfter=2,
        alignment=TA_CENTER,
        fontName="Helvetica",
    )

    # Заголовок секции (Block 1–5)
    styles["section_header"] = ParagraphStyle(
        "section_header",
        parent=base["Heading1"],
        fontSize=14,
        textColor=_COLOR_PRIMARY,
        spaceBefore=14,
        spaceAfter=4,
        fontName="Helvetica-Bold",
        borderPad=0,
    )

    # Подзаголовок внутри секции
    styles["subsection_header"] = ParagraphStyle(
        "subsection_header",
        parent=base["Heading2"],
        fontSize=11,
        textColor=_COLOR_SECONDARY,
        spaceBefore=8,
        spaceAfter=3,
        fontName="Helvetica-Bold",
    )

    # Обычный текст
    styles["body"] = ParagraphStyle(
        "body",
        parent=base["Normal"],
        fontSize=10,
        textColor=_COLOR_SECONDARY,
        spaceAfter=3,
        fontName="Helvetica",
        leading=14,
    )

    # Предупреждение (жёлтый текст)
    styles["warning"] = ParagraphStyle(
        "warning",
        parent=base["Normal"],
        fontSize=9,
        textColor=_COLOR_WARN,
        spaceAfter=4,
        fontName="Helvetica-Oblique",
        leading=13,
    )

    # Нижний колонтитул (forecast omitted и пр.)
    styles["footer_note"] = ParagraphStyle(
        "footer_note",
        parent=base["Normal"],
        fontSize=8,
        textColor=colors.grey,
        spaceAfter=2,
        fontName="Helvetica-Oblique",
        alignment=TA_CENTER,
    )

    # Значение метрики (крупный)
    styles["metric_value"] = ParagraphStyle(
        "metric_value",
        parent=base["Normal"],
        fontSize=13,
        textColor=_COLOR_PRIMARY,
        spaceAfter=1,
        fontName="Helvetica-Bold",
        alignment=TA_RIGHT,
    )

    # Название метрики
    styles["metric_label"] = ParagraphStyle(
        "metric_label",
        parent=base["Normal"],
        fontSize=10,
        textColor=_COLOR_SECONDARY,
        spaceAfter=1,
        fontName="Helvetica",
        alignment=TA_LEFT,
    )

    # Текст ограничения (known limitations / tooltips)
    styles["limitation"] = ParagraphStyle(
        "limitation",
        parent=base["Normal"],
        fontSize=8,
        textColor=colors.grey,
        spaceAfter=2,
        fontName="Helvetica-Oblique",
        leading=11,
    )

    return styles


# ---------------------------------------------------------------------------
# Watermark — наносится на каждую страницу FREE-плана (Section 2)
# ---------------------------------------------------------------------------


class _WatermarkCanvas(canvas.Canvas):
    """
    Расширение canvas.Canvas для нанесения диагональной подложки
    "SubAudit FREE" на каждую страницу (Section 2 — PDF with watermark).
    Используется ТОЛЬКО для плана 'free'.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict] = []

    def showPage(self) -> None:  # type: ignore[override]
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:  # type: ignore[override]
        """Добавляет подложку на все сохранённые страницы перед записью."""
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_watermark()
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def _draw_watermark(self) -> None:
        """Рисует диагональную полупрозрачную надпись на текущей странице."""
        self.saveState()
        self.setFont("Helvetica-Bold", 52)
        self.setFillColor(_COLOR_WATERMARK)
        width, height = A4
        self.translate(width / 2, height / 2)
        self.rotate(45)
        self.drawCentredString(0, 0, _WATERMARK_TEXT)
        self.restoreState()


# ---------------------------------------------------------------------------
# Строители блоков метрик
# ---------------------------------------------------------------------------


def _metric_row(
    label: str,
    value: str,
    styles: dict[str, ParagraphStyle],
) -> list:
    """
    Возвращает строку таблицы [Paragraph(label), Paragraph(value)].
    Используется для единообразного отображения пар метрика–значение.
    """
    return [
        Paragraph(label, styles["metric_label"]),
        Paragraph(value, styles["metric_value"]),
    ]


def _build_metrics_table(rows: list[list], col_widths: list[float]) -> Table:
    """
    Создаёт стилизованную таблицу метрик с чередующимся фоном.
    """
    tbl = Table(rows, colWidths=col_widths)
    tbl_style = TableStyle(
        [
            # Общий фон
            ("BACKGROUND", (0, 0), (-1, -1), _COLOR_LIGHT_BG),
            # Внешняя рамка
            ("BOX", (0, 0), (-1, -1), 0.5, _COLOR_BORDER),
            # Внутренние горизонтальные линии
            ("LINEBELOW", (0, 0), (-1, -2), 0.3, _COLOR_BORDER),
            # Отступы внутри ячеек
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            # Вертикальное выравнивание по центру
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
    )
    tbl.setStyle(tbl_style)
    return tbl


# ---------------------------------------------------------------------------
# Секция: Block 1 — Revenue (Section 6)
# ---------------------------------------------------------------------------


def _section_revenue(
    story: list,
    metrics: dict,
    currency: str,
    styles: dict[str, ParagraphStyle],
    page_width: float,
) -> None:
    """
    Block 1 — Revenue метрики (Section 9: Block 1).
    Формулы: MRR, ARR, ARPU, Total Revenue (Section 6).
    Доступен для всех планов (Section 2 — Metric blocks Basic Blocks 1–2).
    """
    story.append(Paragraph("Block 1 — Revenue", styles["section_header"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=_COLOR_BORDER))
    story.append(Spacer(1, 4))

    col_w = [page_width * 0.6, page_width * 0.4]
    rows = [
        _metric_row("MRR (Monthly Recurring Revenue)",
                    _fmt_currency(metrics.get("mrr"), currency), styles),
        _metric_row("ARR (Annual Recurring Revenue)",
                    _fmt_currency(metrics.get("arr"), currency), styles),
        _metric_row("ARPU (Average Revenue Per User)",
                    _fmt_currency(metrics.get("arpu"), currency), styles),
        _metric_row("Total Revenue (all time)",
                    _fmt_currency(metrics.get("total_revenue"), currency), styles),
    ]
    story.append(_build_metrics_table(rows, col_w))
    story.append(Spacer(1, 8))


# ---------------------------------------------------------------------------
# Секция: Block 2 — Growth (Section 6)
# ---------------------------------------------------------------------------


def _section_growth(
    story: list,
    metrics: dict,
    currency: str,
    styles: dict[str, ParagraphStyle],
    page_width: float,
) -> None:
    """
    Block 2 — Growth метрики (Section 9: Block 2).
    Доступен для всех планов (Section 2 — Metric blocks Basic Blocks 1–2).
    Формулы: New MRR, Reactivation MRR, Growth Rate, Subscribers (Section 6).
    """
    story.append(Paragraph("Block 2 — Growth", styles["section_header"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=_COLOR_BORDER))
    story.append(Spacer(1, 4))

    col_w = [page_width * 0.6, page_width * 0.4]
    rows = [
        _metric_row("New MRR",
                    _fmt_currency(metrics.get("new_mrr"), currency), styles),
        _metric_row("Reactivation MRR",
                    _fmt_currency(metrics.get("reactivation_mrr"), currency), styles),
        _metric_row("MoM Growth Rate",
                    _fmt_percent(metrics.get("growth_rate")), styles),
        _metric_row("New Subscribers (this month)",
                    _fmt_int(metrics.get("new_subscribers")), styles),
        _metric_row("Reactivated Subscribers",
                    _fmt_int(metrics.get("reactivated_subscribers")), styles),
    ]
    story.append(_build_metrics_table(rows, col_w))
    story.append(Spacer(1, 8))


# ---------------------------------------------------------------------------
# Секция: Block 3 — Retention (Section 6)
# ---------------------------------------------------------------------------


def _section_retention(
    story: list,
    metrics: dict,
    currency: str,
    styles: dict[str, ParagraphStyle],
    page_width: float,
) -> None:
    """
    Block 3 — Retention (Section 9: Block 3).
    Доступен: Starter и Pro (Section 2 — All 5 blocks).
    Формулы: Churn Rate, Revenue Churn, NRR (Section 6 / Section 8).
    NRR > 200%: показываем предупреждение (Section 6).
    """
    story.append(Paragraph("Block 3 — Retention", styles["section_header"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=_COLOR_BORDER))
    story.append(Spacer(1, 4))

    col_w = [page_width * 0.6, page_width * 0.4]
    rows = [
        _metric_row("Churn Rate",
                    _fmt_percent(metrics.get("churn_rate")), styles),
        _metric_row("Revenue Churn",
                    _fmt_currency(metrics.get("revenue_churn"), currency), styles),
        _metric_row("NRR (Net Revenue Retention)",
                    _fmt_percent(metrics.get("nrr")), styles),
    ]
    story.append(_build_metrics_table(rows, col_w))

    # NRR > 200% — обязательное предупреждение (Section 6)
    nrr_val = metrics.get("nrr")
    if nrr_val is not None and nrr_val > _NRR_WARNING_THRESHOLD:
        story.append(Spacer(1, 4))
        story.append(
            Paragraph(
                "⚠ NRR exceeds 200% — likely caused by limited prior-month data. "
                "Interpret with caution.",
                styles["warning"],
            )
        )

    story.append(Spacer(1, 8))


# ---------------------------------------------------------------------------
# Секция: Block 4 — Health (Section 6)
# ---------------------------------------------------------------------------


def _section_health(
    story: list,
    metrics: dict,
    currency: str,
    styles: dict[str, ParagraphStyle],
    page_width: float,
) -> None:
    """
    Block 4 — Health (Section 9: Block 4).
    Доступен: Starter и Pro (Section 2).
    Формулы: LTV, Active/Lost/Existing Subscribers (Section 6).
    LTV cap = 36 месяцев — примечание ОБЯЗАТЕЛЬНО (Section 6).
    """
    story.append(Paragraph("Block 4 — Health", styles["section_header"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=_COLOR_BORDER))
    story.append(Spacer(1, 4))

    col_w = [page_width * 0.6, page_width * 0.4]
    rows = [
        _metric_row("LTV (Lifetime Value)",
                    _fmt_currency(metrics.get("ltv"), currency), styles),
        _metric_row("Active Subscribers",
                    _fmt_int(metrics.get("active_subscribers")), styles),
        _metric_row("Lost Subscribers",
                    _fmt_int(metrics.get("lost_subscribers")), styles),
        _metric_row("Existing Subscribers (retained)",
                    _fmt_int(metrics.get("existing_subscribers")), styles),
    ]
    story.append(_build_metrics_table(rows, col_w))

    # Обязательное примечание по LTV cap=36 (Section 6)
    story.append(Spacer(1, 4))
    story.append(
        Paragraph(
            "* LTV capped at 36 months (ARPU × 36) when churn rate = 0. "
            "At 2–3% monthly churn, true LTV is 33–108% higher than the capped value. "
            "Do NOT use capped LTV for unit economics or CAC payback decisions.",
            styles["limitation"],
        )
    )
    story.append(Spacer(1, 8))


# ---------------------------------------------------------------------------
# Секция: Block 5 — Cohort (Section 7)
# ---------------------------------------------------------------------------


def _section_cohort(
    story: list,
    metrics: dict,
    styles: dict[str, ParagraphStyle],
    page_width: float,
) -> None:
    """
    Block 5 — Cohort Table (Section 7, Section 9: Block 5).
    Доступен: Starter и Pro (Section 2).
    Минимум 3 когортных месяца — иначе None (Section 7).
    Рендерим как таблицу: до 8 последних когорт (оптимизировано для читаемости).
    Весь блок обёрнут в KeepTogether для предотвращения разрыва между страницами.
    """
    cohort_df = metrics.get("cohort_table")  # DataFrame или None (Section 9)

    if cohort_df is None:
        # Если данных нет, добавляем простое сообщение без KeepTogether
        story.append(Paragraph("Block 5 — Cohort Retention Analysis", styles["section_header"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=_COLOR_BORDER))
        story.append(Spacer(1, 4))
        story.append(
            Paragraph(
                "Cohort table not available — at least 3 distinct cohort months required.",
                styles["body"],
            )
        )
        story.append(Spacer(1, 8))
        return

    # Создаём список элементов для KeepTogether
    block_elements = []

    # Заголовок секции
    block_elements.append(Paragraph("Block 5 — Cohort Retention Analysis", styles["section_header"]))
    block_elements.append(HRFlowable(width="100%", thickness=0.5, color=_COLOR_BORDER))
    block_elements.append(Spacer(1, 4))

    # Берём максимум 8 последних когорт (оптимизировано для книжного формата)
    cohort_display = cohort_df.tail(8)

    # Строим заголовок таблицы
    col_labels = ["Cohort"] + list(cohort_display.columns)
    header_row = [Paragraph(str(c), ParagraphStyle(
        "ch",
        fontName="Helvetica-Bold",
        fontSize=7,
        textColor=colors.white,
        alignment=TA_CENTER,
    )) for c in col_labels]

    data_rows = [header_row]
    for cohort_month, row in cohort_display.iterrows():
        cells = [Paragraph(str(cohort_month), ParagraphStyle(
            "cb",
            fontName="Helvetica-Bold",
            fontSize=7,
            textColor=_COLOR_SECONDARY,
        ))]
        for val in row:
            if val is None or (isinstance(val, float) and math.isnan(val)):
                display_val = "—"
            else:
                display_val = f"{val:.1f}%"
            cells.append(Paragraph(display_val, ParagraphStyle(
                "cv",
                fontName="Helvetica",
                fontSize=7,
                textColor=_COLOR_SECONDARY,
                alignment=TA_CENTER,
            )))
        data_rows.append(cells)

    # Оптимизированная ширина колонок для 8 когорт
    num_cols = len(col_labels)
    col_widths = [page_width * 0.16] + [
        page_width * 0.84 / max(num_cols - 1, 1)
    ] * (num_cols - 1)

    cohort_tbl = Table(data_rows, colWidths=col_widths)
    cohort_tbl.setStyle(
        TableStyle(
            [
                # Заголовок — синий фон
                ("BACKGROUND", (0, 0), (-1, 0), _COLOR_PRIMARY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                # Чередование строк
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [_COLOR_LIGHT_BG, colors.white]),
                ("BOX", (0, 0), (-1, -1), 0.5, _COLOR_BORDER),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, _COLOR_BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    block_elements.append(cohort_tbl)
    block_elements.append(Spacer(1, 6))

    # Легенда: объяснение retention % и цветовой раскраски
    block_elements.append(
        Paragraph(
            "<b>How to read:</b> Each cohort shows % of customers retained over time. "
            "Month 0 = first purchase (always 100%). "
            "Higher retention % = better customer loyalty.",
            styles["body"],
        )
    )
    block_elements.append(Spacer(1, 3))
    block_elements.append(
        Paragraph(
            "* Cohort retention: customer_id has ≥1 active row in that calendar month "
            "(amount not checked — paused/discounted subscriptions count as retained). "
            "Section 7 — intentional asymmetry.",
            styles["limitation"],
        )
    )
    block_elements.append(Spacer(1, 8))

    # Оборачиваем весь блок в KeepTogether для предотвращения разрыва
    story.append(KeepTogether(block_elements))


# ---------------------------------------------------------------------------
# Секция: Forecast (Section 10)
# ---------------------------------------------------------------------------


def _section_forecast(
    story: list,
    forecast_dict: dict | None,
    styles: dict[str, ParagraphStyle],
    page_width: float,
) -> None:
    """
    Секция прогноза (Section 10).
    Forecast gate: если forecast_dict is None → показываем footer-сообщение
    "Forecast omitted — fewer than 6 months of data available." (Section 10).
    Экспорт разрешён только при data_months_used >= 6 (Section 10).
    Сценарии: Pessimistic / Realistic / Optimistic (Section 10).
    """
    story.append(Paragraph("Forecast (12-month)", styles["section_header"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=_COLOR_BORDER))
    story.append(Spacer(1, 4))

    # Forecast gate (Section 10 — export gate)
    if forecast_dict is None:
        story.append(
            Paragraph(
                _FORECAST_OMITTED_FOOTER,
                styles["footer_note"],
            )
        )
        story.append(Spacer(1, 8))
        return

    # Предупреждение при 3–5 месяцах данных — только Realistic (Section 10)
    data_months = forecast_dict.get("data_months_used", 0)
    if 3 <= data_months <= 5:
        story.append(
            Paragraph(
                "⚠ Forecast based on fewer than 6 months of data — "
                "only Realistic scenario available. Statistical confidence is limited.",
                styles["warning"],
            )
        )
        story.append(Spacer(1, 4))

    # Отображаем сводку сценариев (Section 10 — Pessimistic / Realistic / Optimistic)
    scenarios_available = forecast_dict.get("scenarios", {})
    col_w = [page_width * 0.4, page_width * 0.3, page_width * 0.3]

    header = [
        Paragraph("Month", ParagraphStyle("fh", fontName="Helvetica-Bold",
                                          fontSize=9, textColor=colors.white,
                                          alignment=TA_CENTER)),
        Paragraph("Scenario", ParagraphStyle("fh", fontName="Helvetica-Bold",
                                             fontSize=9, textColor=colors.white,
                                             alignment=TA_CENTER)),
        Paragraph("Projected MRR", ParagraphStyle("fh", fontName="Helvetica-Bold",
                                                  fontSize=9, textColor=colors.white,
                                                  alignment=TA_CENTER)),
    ]
    rows = [header]

    # Для каждого сценария берём последний (12-й) месяц прогноза как итог
    scenario_order = ["pessimistic", "realistic", "optimistic"]
    scenario_labels = {
        "pessimistic": "Pessimistic",
        "realistic": "Realistic",
        "optimistic": "Optimistic",
    }

    for sc_key in scenario_order:
        sc_data = scenarios_available.get(sc_key)
        if sc_data is None:
            continue  # Сценарий недоступен (3–5 мес → только realistic, Section 10)
        # sc_data — список значений yhat по месяцам (12 точек)
        values = sc_data if isinstance(sc_data, list) else []
        if not values:
            continue

        # Показываем финальное (12-е) предсказанное значение и месяц
        final_val = values[-1]
        final_month = f"Month +{len(values)}"
        rows.append([
            Paragraph(final_month, ParagraphStyle(
                "fd", fontName="Helvetica", fontSize=9,
                textColor=_COLOR_SECONDARY, alignment=TA_CENTER)),
            Paragraph(scenario_labels[sc_key], ParagraphStyle(
                "fd", fontName="Helvetica", fontSize=9,
                textColor=_COLOR_SECONDARY, alignment=TA_CENTER)),
            Paragraph(f"{final_val:,.2f}", ParagraphStyle(
                "fd", fontName="Helvetica-Bold", fontSize=9,
                textColor=_COLOR_PRIMARY, alignment=TA_CENTER)),
        ])

    if len(rows) > 1:
        fc_tbl = Table(rows, colWidths=col_w)
        fc_tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), _COLOR_PRIMARY),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                     [_COLOR_LIGHT_BG, colors.white]),
                    ("BOX", (0, 0), (-1, -1), 0.5, _COLOR_BORDER),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.3, _COLOR_BORDER),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(fc_tbl)

    story.append(Spacer(1, 4))
    story.append(
        Paragraph(
            "Forecast model: Holt-Winters exponential smoothing (statsmodels). "
            "Pessimistic: churn ×1.20 | Realistic: as-is | Optimistic: churn ×0.80. "
            "Negative values clamped to 0. Section 10.",
            styles["limitation"],
        )
    )
    story.append(Spacer(1, 8))


# ---------------------------------------------------------------------------
# Секция: Simulation (PRO only, Section 11)
# ---------------------------------------------------------------------------


def _section_simulation(
    story: list,
    simulation_dict: dict | None,
    currency: str,
    styles: dict[str, ParagraphStyle],
    page_width: float,
) -> None:
    """
    Секция симуляции — доступна ТОЛЬКО для PRO (Section 2, Section 11).
    base_arpu == 0 guard: если simulation_dict is None — секция опускается.
    Предупреждение об однородности ARPU ОБЯЗАТЕЛЬНО (Section 11 known limitation).
    """
    story.append(Paragraph("Simulation (PRO)", styles["section_header"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=_COLOR_BORDER))
    story.append(Spacer(1, 4))

    if simulation_dict is None:
        # base_arpu == 0 guard (Section 11) или данные недоступны
        story.append(
            Paragraph(
                "Simulation not available — ARPU is zero or simulation could not be "
                "computed for this dataset.",
                styles["body"],
            )
        )
        story.append(Spacer(1, 8))
        return

    col_w = [page_width * 0.6, page_width * 0.4]

    # Входные параметры симуляции (Section 11 — Input Parameters)
    params = simulation_dict.get("params", {})
    inputs_rows = []
    if "churn_reduction" in params:
        inputs_rows.append(
            _metric_row(
                "Churn Reduction",
                f"{params['churn_reduction'] * 100:.1f}%",
                styles,
            )
        )
    if "new_customers_month" in params:
        inputs_rows.append(
            _metric_row(
                "New Customers / Month",
                _fmt_int(params.get("new_customers_month")),
                styles,
            )
        )
    if "price_increase" in params:
        inputs_rows.append(
            _metric_row(
                "Price Increase",
                f"{params['price_increase'] * 100:.1f}%",
                styles,
            )
        )

    if inputs_rows:
        story.append(Paragraph("Input Parameters", styles["subsection_header"]))
        story.append(_build_metrics_table(inputs_rows, col_w))
        story.append(Spacer(1, 6))

    # Результаты симуляции
    results = simulation_dict.get("results", {})
    result_rows = []

    final_mrr = results.get("final_mrr")
    if final_mrr is not None:
        result_rows.append(
            _metric_row("Projected MRR (Month 12)",
                        _fmt_currency(final_mrr, currency), styles)
        )

    mrr_change_pct = results.get("mrr_change_pct")
    result_rows.append(
        _metric_row(
            "MRR Change %",
            # mrr_change_pct = None когда base_mrr == 0 (Section 11)
            _fmt_percent(mrr_change_pct) if mrr_change_pct is not None else "N/A",
            styles,
        )
    )

    net_new_customers = results.get("net_new_customers")
    if net_new_customers is not None:
        result_rows.append(
            _metric_row("Net New Customers (12 mo)",
                        _fmt_int(net_new_customers), styles)
        )

    if result_rows:
        story.append(Paragraph("12-Month Projection", styles["subsection_header"]))
        story.append(_build_metrics_table(result_rows, col_w))

    # Обязательное предупреждение об однородности ARPU (Section 11 — tooltip)
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            "⚠ Results assume uniform ARPU. With mixed pricing tiers, actual revenue "
            "impact may differ by 30–60%. Mixed-tier modelling is v2 roadmap. "
            "Base MRR decays exponentially each month by new_churn_rate — correct "
            "SaaS churn modelling. (Section 11)",
            styles["warning"],
        )
    )
    story.append(Spacer(1, 8))


# ---------------------------------------------------------------------------
# Страница обложки
# ---------------------------------------------------------------------------


def _build_cover_page(
    story: list,
    plan: str,
    company_name: dict,
    currency: str,
    styles: dict[str, ParagraphStyle],
) -> None:
    """
    Строит страницу обложки.
    PRO — branded (company name отображается) (Section 2).
    Starter / Free — название компании не выводится.
    display_name берётся из company_name['display_name'] (Section 14).
    """
    story.append(Spacer(1, 40 * mm))

    story.append(Paragraph("SubAudit", styles["doc_title"]))
    story.append(Spacer(1, 4))

    story.append(
        Paragraph("Subscription Analytics Report", styles["doc_subtitle"])
    )
    story.append(Spacer(1, 6))

    # Branded title — только PRO (Section 2)
    if plan == _PLAN_PRO:
        display_name = company_name.get("display_name", "")
        if display_name:
            story.append(
                Paragraph(display_name, styles["doc_subtitle"])
            )

    story.append(Spacer(1, 4))

    # Дата генерации
    now_str = datetime.utcnow().strftime("%B %d, %Y at %H:%M UTC")
    story.append(Paragraph(f"Generated: {now_str}", styles["doc_date"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"Currency: {currency}", styles["doc_date"]))
    story.append(Spacer(1, 4))

    # Указание плана
    plan_display = {"free": "FREE", "starter": "Starter ($9/mo)",
                    "pro": "Pro ($19/mo)"}.get(plan, plan.upper())
    story.append(Paragraph(f"Plan: {plan_display}", styles["doc_date"]))

    story.append(Spacer(1, 20 * mm))
    story.append(HRFlowable(width="80%", thickness=1, color=_COLOR_PRIMARY))
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            "Files are processed in-memory and NEVER stored or sent to third parties.",
            ParagraphStyle(
                "privacy",
                fontName="Helvetica-Oblique",
                fontSize=9,
                textColor=_COLOR_SECONDARY,
                alignment=TA_CENTER,
            ),
        )
    )

    story.append(PageBreak())


# ---------------------------------------------------------------------------
# Основная функция generate_pdf() (Section 4)
# ---------------------------------------------------------------------------


def generate_pdf(
    metrics_dict: dict,
    forecast_dict: dict | None,
    simulation_dict: dict | None,
    plan: str,
    company_name: dict,
    currency: str,
    data_quality_flags: dict,
) -> bytes:
    """
    Генерирует PDF-отчёт и возвращает bytes.

    Параметры:
        metrics_dict      — dict от get_all_metrics() (Section 9)
        forecast_dict     — dict или None; None → forecast gate (Section 10)
        simulation_dict   — dict или None; PRO only (Section 11)
        plan              — 'free' / 'starter' / 'pro' (Section 2)
                            ВАЖНО: план должен быть верифицирован через Gumroad
                            ДО вызова этой функции — Checkpoint 3 (Section 13)
        company_name      — {'display_name': str, 'filename_safe_name': str} (Section 14)
        currency          — str, например 'USD' (Section 14)
        data_quality_flags — dict с ключами prev_month_status, last_month_is_fallback,
                             last_month_used (Section 14)

    Возвращает:
        bytes — готовый PDF-документ

    Логика watermark (Section 2):
        FREE    → диагональная подложка "_WATERMARK_TEXT" на каждой странице
        Starter → без подложки
        PRO     → без подложки + branded (company name на обложке)

    Forecast gate (Section 10):
        forecast_dict is None → вместо секции выводится:
        "Forecast omitted — fewer than 6 months of data available."

    Simulation (Section 11):
        simulation_dict is None → секция симуляции говорит "not available"
        simulation отображается ТОЛЬКО для плана 'pro'

    Блоки метрик (Section 2):
        FREE    → Block 1 + Block 2 (Basic)
        Starter → Block 1–5
        PRO     → Block 1–5 + Simulation
    """

    # -----------------------------------------------------------------------
    # Буфер для записи PDF в память (никаких дисковых файлов)
    # -----------------------------------------------------------------------
    buffer = io.BytesIO()

    # -----------------------------------------------------------------------
    # Выбор canvas-класса по плану (Section 2 — watermark logic)
    # FREE → _WatermarkCanvas, Starter/Pro → обычный canvas.Canvas
    # -----------------------------------------------------------------------
    canvas_class = _WatermarkCanvas if plan == _PLAN_FREE else canvas.Canvas

    # -----------------------------------------------------------------------
    # Настройка документа
    # -----------------------------------------------------------------------
    page_w, page_h = A4
    margin = 18 * mm
    usable_width = page_w - 2 * margin

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="SubAudit Report",
        author="SubAudit",
        subject="Subscription Analytics",
        creator="SubAudit v1.0",
    )

    # Переопределяем canvas фабрику для водяного знака
    # (SimpleDocTemplate принимает canvasmaker в .build())
    styles = _build_styles()
    story: list = []

    # -----------------------------------------------------------------------
    # Обложка (Section 2, Section 14)
    # -----------------------------------------------------------------------
    _build_cover_page(story, plan, company_name, currency, styles)

    # -----------------------------------------------------------------------
    # Предупреждение о качестве данных (Section 14 — data_quality_flags)
    # -----------------------------------------------------------------------
    prev_month_status = data_quality_flags.get("prev_month_status", "ok")
    last_month_is_fallback = data_quality_flags.get("last_month_is_fallback", False)
    last_month_used = data_quality_flags.get("last_month_used")

    data_quality_warnings = []

    if last_month_is_fallback:
        # Fallback UI warning (Section 5 — "last month" definition)
        data_quality_warnings.append(
            "⚠ Last month used: fallback mode — fewer than 5 unique active customers "
            f"in the most recent month ({last_month_used}). Metrics may be unreliable."
        )

    if prev_month_status == "gap":
        # Gap в данных — некоторые метрики вернут None (Section 5)
        data_quality_warnings.append(
            "⚠ Gap detected in month sequence — Growth Rate, Churn Rate, "
            "NRR, Lost/Existing Subscribers display N/A."
        )
    elif prev_month_status == "missing":
        data_quality_warnings.append(
            "⚠ Previous month data is missing — comparative metrics display N/A."
        )

    if data_quality_warnings:
        story.append(Paragraph("Data Quality Notices", styles["section_header"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=_COLOR_BORDER))
        story.append(Spacer(1, 4))
        for w_text in data_quality_warnings:
            story.append(Paragraph(w_text, styles["warning"]))
        story.append(Spacer(1, 8))

    # -----------------------------------------------------------------------
    # Block 1 — Revenue (все планы, Section 2)
    # -----------------------------------------------------------------------
    _section_revenue(story, metrics_dict, currency, styles, usable_width)

    # -----------------------------------------------------------------------
    # Block 2 — Growth (все планы, Section 2)
    # -----------------------------------------------------------------------
    _section_growth(story, metrics_dict, currency, styles, usable_width)

    # -----------------------------------------------------------------------
    # Block 3–5 — только Starter и Pro (Section 2)
    # -----------------------------------------------------------------------
    if plan in (_PLAN_STARTER, _PLAN_PRO):
        _section_retention(story, metrics_dict, currency, styles, usable_width)
        _section_health(story, metrics_dict, currency, styles, usable_width)
        # Block 5 (Cohort Table) начинается с новой страницы для лучшей читаемости
        story.append(PageBreak())
        _section_cohort(story, metrics_dict, styles, usable_width)

    # -----------------------------------------------------------------------
    # Forecast (Starter + Pro, Section 2 + Section 10)
    # Для FREE — прогноз недоступен (Section 2), раздел не включаем
    # -----------------------------------------------------------------------
    if plan in (_PLAN_STARTER, _PLAN_PRO):
        story.append(PageBreak())
        _section_forecast(story, forecast_dict, styles, usable_width)

    # -----------------------------------------------------------------------
    # Simulation — только PRO (Section 2, Section 11)
    # -----------------------------------------------------------------------
    if plan == _PLAN_PRO:
        _section_simulation(story, simulation_dict, currency, styles, usable_width)

    # -----------------------------------------------------------------------
    # Финальный нижний колонтитул (forecast gate notice если блокирован)
    # Section 10 — "Footer: Forecast omitted..."
    # -----------------------------------------------------------------------
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=0.5, color=_COLOR_BORDER))
    story.append(Spacer(1, 4))

    # Дублируем forecast-footer внизу документа (Section 10 требует footer)
    if forecast_dict is None and plan in (_PLAN_STARTER, _PLAN_PRO):
        story.append(
            Paragraph(_FORECAST_OMITTED_FOOTER, styles["footer_note"])
        )

    story.append(
        Paragraph(
            f"SubAudit v1.0 · Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} · "
            "Files are processed in-memory and NEVER stored or sent to third parties.",
            styles["footer_note"],
        )
    )

    # -----------------------------------------------------------------------
    # Сборка PDF
    # canvasmaker=canvas_class — передаём наш _WatermarkCanvas для FREE
    # -----------------------------------------------------------------------
    doc.build(story, canvasmaker=canvas_class)

    # -----------------------------------------------------------------------
    # Возвращаем bytes (Section 4 — generate_pdf() → bytes)
    # -----------------------------------------------------------------------
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


# ---------------------------------------------------------------------------
# Вспомогательная функция: безопасное имя файла (Section 4, Section 14)
# ---------------------------------------------------------------------------


def get_pdf_filename(company_name: dict, plan: str) -> str:
    """
    Возвращает безопасное имя файла для скачивания PDF.

    Использует company_name['filename_safe_name'] (Section 14).
    PRO: 'SubAudit_Report_<CompanyName>_<date>.pdf'
    Starter/Free: 'SubAudit_Report_<date>.pdf'
    """
    date_str = datetime.utcnow().strftime("%Y%m%d")
    if plan == _PLAN_PRO:
        # filename_safe_name — уже очищенная строка (Section 14)
        safe_name = company_name.get("filename_safe_name", "")
        if safe_name:
            return f"SubAudit_Report_{safe_name}_{date_str}.pdf"
    return f"SubAudit_Report_{date_str}.pdf"
