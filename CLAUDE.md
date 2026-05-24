# SubAudit — CLAUDE.md
## Инструкции для Claude Code и других AI-ассистентов

**Последнее обновление:** 2026-05-30 (v3.3 завершён)

---

## Главные документы (в порядке приоритета)

1. **[SPEC.md](./SPEC.md)** — техническая спецификация, источник истины
2. **[STRATEGY.md](./STRATEGY.md)** — бизнес-стратегия, реальные боли пользователей
3. **Этот файл** — как работать с AI-ассистентом

При конфликте между документами приоритет: SPEC > STRATEGY > этот файл.
**Старый `SubAudit_Spec.docx` удалён. Не искать его.**

---

## Кто я и что строю

Я — соло-разработчик без бюджета, делаю **SubAudit** —
SaaS аналитику подписок для non-Stripe микро-фаундеров.

**Ключевой контекст:**
- Денег на инфраструктуру нет — все сервисы на free tier
- Целевая аудитория: B2B, англоязычные, $1K-50K MRR
- Главный конкурент — Google Sheets, не ChartMogul
- Главное преимущество — CSV upload (любой источник), $9 вместо $99

**Язык интерфейса:** английский. **Язык комментариев в коде:** русский.

Подробнее об аудитории и позиционировании: [STRATEGY.md](./STRATEGY.md).

---

## Технический стек

См. [SPEC.md §4](./SPEC.md#4-tech-stack-frozen-until-500-mrr).

Кратко: Python 3.11.9 + Streamlit 1.35 + Supabase + Gumroad + Sentry.
**Все на free tier. Менять только после $500 MRR.**

---

## Текущий roadmap (приоритет по валидированной боли)

Источник правды: [SPEC.md §8](./SPEC.md#8-roadmap-priority-by-validated-pain).

| # | Фича | Срок | Зачем |
|---|------|------|-------|
| v3.1 | Voluntary vs Involuntary Churn split | 1 день | ✅ ЗАВЕРШЕНО — уникальная фича, никто не делает |
| v3.2 | Multi-source CSV presets | 2-3 дня | ✅ ЗАВЕРШЕНО — главный дифференциатор от ChartMogul |
| v3.3 | Snapshot history (Supabase, 6 подшагов) | 2-3 дня | ✅ ЗАВЕРШЕНО — retention механика |


**Детализация v3.2 (текущий фокус):**

| # | Подшаг | Статус | Что делает |
|---|--------|--------|-----------|
| v3.2.1 | Каталог сигнатур | ✅ ЗАВЕРШЕНО | `_PRESET_SIGNATURES` в `app/core/presets.py` для 6 источников |
| v3.2.2 | Детектор формата | ✅ ЗАВЕРШЕНО | `detect_preset(df, columns)`, 25 тестов |
| v3.2.3 | Интеграция в upload flow | ✅ ЗАВЕРШЕНО | Вызов detect_preset() после парсинга CSV, сохранение в session_state |
| v3.2.4 | UI на mapping-странице | ✅ ЗАВЕРШЕНО | Зелёный баннер + предзаполнение из пресета + кнопка сброса; 341 тест |
| v3.2.5 | Авто-скип mapping | ✅ ЗАВЕРШЕНО | Пропуск mapping при распознанном формате (чекбокс, default ON), 353 теста |
| v3.2.6 | Документация + тесты | ✅ ЗАВЕРШЕНО | FAQ, help, SPEC.md, CLAUDE.md обновлены, 353 теста проходят |

**Не браться за фичу, которой нет в roadmap, без обновления SPEC.md.**

---

## Текущий статус проекта (2026-05-22)

### ✅ ЗАВЕРШЕНО

| Задача | Статус | Примечания |
|--------|--------|-----------|
| Реорганизация документации v3.0 | ✅ | Docx удалён, созданы SPEC.md + STRATEGY.md, CLAUDE.md переписан |
| Переезд LemonSqueezy → Gumroad | ✅ | Все 25 тестов payments проходят |
| Полный тест-сьют v3.1 | ✅ | **308/308 тестов проходят** (добавлены 8 тестов voluntary/involuntary churn) |
| v3.2.1 Каталог сигнатур | ✅ | Словарь `_PRESET_SIGNATURES` в `app/core/presets.py` для 6 источников |
| v3.2.2 Детектор формата | ✅ | `detect_preset(df, columns)`, 25 тестов, 333/333 pass |
| Фикс forecast HoltWinters | ✅ | initialization_method="estimated", формулы сценариев корректны |

### ⚠️ Предупреждения (не блокирующие)

| Предупреждение | Приоритет | Когда чинить |
|----------------|-----------|-------------|
| `RequestsDependencyWarning` от urllib3 | Низкий | При обновлении зависимостей |
| `DeprecationWarning` от `gotrue` → `supabase_auth` | Средний | До обновления Supabase SDK |

### ✅ v3.2 полностью завершён

Все 6 подшагов v3.2 выполнены. 353 теста проходят. Multi-source CSV presets работают.

### ✅ v3.3 полностью завершён (2026-05-30)

**Snapshot history.** 6 подшагов выполнены. 409 тестов проходят.
Сохранение метрик после каждой загрузки CSV, MoM-дельта на дашборде,
график MRR/Churn по месяцам, список снапшотов на странице аккаунта + CSV-экспорт.

### 🔜 Следующий этап

**v4 (отложено до валидации платящими пользователями)**
- Stripe / Paddle / Gumroad direct integrations (OAuth)
- Scheduled email reports
- Public share links


### План анонса v3.3

**Reddit (r/SaaS):** *"Upload your CSV once, SubAudit remembers your metrics month-over-month. See MRR, Churn, and NRR trends over time. No integrations — just re-upload next month. Free plan included."*

**IndieHackers:** *"Shipping v3.3 — snapshot history. Your dashboard now shows MoM changes after just 2 uploads. Supabase-backed, free for all plans. Because you shouldn't need a spreadsheet to track if you're growing."*

### План анонса v3.2

**Reddit (r/SaaS):** *"I built a free tool that auto-detects CSV exports from Stripe, Paddle, Gumroad, LemonSqueezy, Chargebee, and manual invoices. Upload any billing export and skip the column mapping entirely. No integrations needed. $0 on Free plan."*

**IndieHackers:** *"Shipping v3.2 — multi-source CSV presets. SubAudit now recognizes 6 billing sources and auto-maps your columns on upload. Green badge shows which format was detected. Manual override available. Because SaaS founders use more than just Stripe."*

### План анонса v3.1

**Reddit (r/SaaS):** *"Stripe hides a critical metric from you — involuntary churn. I built a free tool that splits churn into 'cancelled' vs 'payment failed'. Turns out 30-40% of 'churn' is just expired cards. You can fix that with dunning emails, but only if you see it."*

**IndieHackers:** *"Shipping v3.1 — voluntary vs involuntary churn split. Your dashboard now separates customers who hated your product from those whose card expired. Actionable insight Stripe won't give you. CSV upload, no integration, $0 on Free plan."*

---"

---

## Anti-patterns (что НЕ делать)

Эти правила выведены из неудачных подходов прошлых версий проекта:

1. ❌ **Не делать фичи без валидированной боли.** Каждая фича должна
   ссылаться на реальный пост / комментарий пользователя. Гипотезы — нет.

2. ❌ **Не делать косметику до $500 MRR.** Шрифты, анимации, иконки,
   редизайн landing — это прокрастинация под видом работы. Только если
   PostHog покажет конкретную точку отвала из-за UI.

3. ❌ **Не повышать цены, пока нет 10 платящих.** "Charge more" — это
   совет для людей с product-market fit. У нас его пока нет.

4. ❌ **Не строить интеграции (Stripe OAuth, webhooks) до v4.** Это
   недели работы под невалидированный спрос. CSV presets (v3.2) дают
   80% ценности за 5% усилий.

5. ❌ **Не добавлять платные сервисы.** Если решение требует Mailgun /
   Sentry paid / домен — сначала спросить.

6. ❌ **Не предлагать фичи из старого PRODUCT_STRATEGY.md** (Health Score,
   benchmarks, scheduled reports, share links, team seats). На Reddit
   никто этого не просит. Эти идеи помечены как "drop" в STRATEGY.md §7.

7. ❌ **Не писать новые .md документы без необходимости.** Уже есть
   SPEC, STRATEGY, CLAUDE, README, docs/FAQ, docs/DATA_PREPARATION.
   Этого хватает.

---

## Definition of Done (для каждой новой фичи)

Фича считается готовой, только если выполнены ВСЕ пункты:

- [ ] Код написан и проходит существующие тесты
- [ ] Добавлен хотя бы один новый тест на новую логику
- [ ] Обновлена соответствующая запись в [SPEC.md §8](./SPEC.md#8-roadmap-priority-by-validated-pain)
- [ ] Если фича видна пользователю — обновлены `docs/FAQ.md` и landing
- [ ] Если фича влияет на тарифы — обновлена таблица в `app/pages/6_pricing.py`
- [ ] Есть план "как объявить" (1-2 предложения для Reddit/IH поста)

Без последнего пункта фича не существует с точки зрения бизнеса.

---

## Workflow для AI-ассистента

### При получении задачи:
1. Прочитать [SPEC.md](./SPEC.md) — техническая истина
2. Сверить с [STRATEGY.md](./STRATEGY.md) — соответствует ли задача целевой аудитории
3. Проверить anti-patterns выше
4. Задать уточняющие вопросы (мало контекста — не угадывать)
5. Получить подтверждение от разработчика
6. Внести изменения шаг за шагом
7. Создать коммит на русском с Co-Authored-By

### Стиль коммитов:
```
fix: краткое описание

Детали:
- Что сделано
- Зачем (со ссылкой на SPEC.md §X или Reddit-источник)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Стиль ответов разработчику:
- Коротко, по существу, на русском
- Без эмодзи кроме критичных предупреждений
- Если предлагается изменение — сначала черновик, потом запись
- Никогда не запускать деструктивные команды без подтверждения

---

## Ключевые правила (обязательно соблюдать)

1. **Иммутабельность DataFrame** — никаких мутаций, кроме `cleaner.py`.
   Проверяется через AST в `test_immutability.py`.
2. **Без записи на диск** — PDF и Excel только через `io.BytesIO`.
3. **`.env` и `secrets.toml`** — никогда не коммитить в git.
4. **DEV-override** — только локально через `.env`. На Streamlit Cloud не ставить.
5. **Перед изменениями** — всегда уточняющие вопросы при неясности.

---

## Что делать при ошибках

### Если разработчик сообщает об ошибке:
1. Проверить логи Sentry (если доступны)
2. Воспроизвести локально через `run.bat`
3. Сверить со SPEC.md — это баг или intentional ограничение?
4. Предложить минимальный фикс (root cause, не симптом)
5. Получить подтверждение перед изменением

### Типичные проблемы:
- **Excel generation failed** → проверить сигнатуру `generate_excel()`
- **Forecast пустой** → проверить `forecast_dict` в `session_state`
- **CSV не загружается** → проверить encoding detection (charset-normalizer)
- **Метрики N/A** → проверить `prev_month_status` в `data_quality_flags`

---

## Что делать, если разработчик просит "что-то улучшить"

Это размытый запрос. Не угадывать. Спросить:

1. Какая конкретная проблема? (баг / производительность / UX / новая фича)
2. Откуда взялась идея? (свой опыт / отзыв пользователя / просто захотелось)
3. Если "просто захотелось" — мягко спросить, не лучше ли сначала закончить
   текущий пункт roadmap.

**Принцип:** AI-ассистент защищает фокус разработчика от собственного
импульса разработчика. Это часть работы.

---

---

## Инструкция для начала новой сессии (читать первой)

При старте нового чата **скопируй этот текст** и отправь AI-ассистенту:

```
Я работаю над проектом SubAudit — SaaS-метрики для подписок (Python 3.11.9, Streamlit).

Перед тем как что-то предлагать, прочитай эти файлы в указанном порядке:
1. SPEC.md — техническая спецификация, источник истины
2. STRATEGY.md — бизнес-стратегия, целевая аудитория, roadmap
3. CLAUDE.md — инструкции для AI-ассистента, anti-patterns, workflow

"После этого прочитай WORKDIR.txt (путь к проекту) и запусти run_tests.bat для проверки тестов.
Затем скажи:"
- какую версию проекта ты видишь
- какой конкретно подшаг следующий (SPEC.md §8, таблица v3.2)
- все ли тесты проходят (результат run_tests.bat)
- есть ли незакоммиченные изменения

ВАЖНО: Мы работаем МАЛЕНЬКИМИ шагами. Один подшаг за сессию (~30-60 мин).
Не начинай следующий подшаг, пока текущий не закоммичен.

Говори на русском. Не предлагай фичи без ссылки на реальную боль пользователя из STRATEGY.md.
```

**Почему это важно:** без этого AI может начать гадать, предлагать удалённые фичи
или игнорировать roadmap. С этим текстом он сразу видит полную картину.

---

*Этот файл читается Claude Code и другими AI автоматически.*
*Если что-то противоречит SPEC.md — побеждает SPEC.md.*
*Если что-то противоречит реальности кода — обновляется SPEC.md, не код.*

