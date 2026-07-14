# Черновик (RU) - журнал событий: `#33725` → тихий bundled-revert в `#35146` и UB type-punning

**Статус:** подробный черновик для подготовки EN Discussion.  
**Публикация:** см. `2026-07-14_tt_metal_layernorm_event_log_final_en.md`.  
**Уровни:** **факт** / **записано** / **first-party** / **открыто**.

---

## За 60 секунд

1. PR `#33725` (миграция `layernorm_post_all_gather` на TMP) был готов в начале декабря 2025, получил approvals (включая maintainer), и был **явно придержан** автором по просьбе models-team ради `#31702`.
2. Reviewer нашёл **union type-punning UB**; автор **в тот же день** заменил на `std::bit_cast`, прошёл по codebase и сообщил, что таких мест много; lead попросил убрать pattern «everywhere».
3. После hang-revert models PR (`#34435`) автор **сам** заребейзил; `#33725` смёржен **2025-12-17**.
4. Через 16 дней гигантский `#35146` (46 files, merge **2026-01-02**, канун/праздничное окно) **внутри себя** откатывает `#33725`, возвращает Welford и заново делает migration. Title говорит про hang в `#31702`. На треде `#33725` **нет** объясняющего комментария автору.
5. На merge `#35146` host снова с `union`; kernel helper `_bit_cast_` снова union. Human review `#35146` **не обсуждает** UB. На внешнем `#33725` тот же класс UB флагнули со стандартом; на внутреннем `#31702` fix отложили.

Это журнал **наблюдаемого процесса**, не вердикт о намерении.

---

## 1. Team play вокруг `#33725` (детально)

### 1.1 Открытие и scope

- **2025-12-03:** открыт [#33725](https://github.com/tenstorrent/tt-metal/pull/33725) - миграция op на новую infra по `DEVICE_OPERATION_MIGRATION_GUIDE.md` (ticket `#32693`). **Факт.**
- Scope - структурная TMP-миграция / registered prim, не алгоритм Welford и не hang-fix Llama.

### 1.2 Reviewer находит UB - и что сделал автор

- **2025-12-04:** `vtsilytskyiTT` на review: это UB; если записан `float`, активного `uint32_t` нет; цитата C++ §9.5 Unions. **Записано.**  
  Permalink: https://github.com/tenstorrent/tt-metal/pull/33725#discussion_r2589099451
- Автор в том же треде указывает на исторический blame (паттерн уже был в коде) и что Copilot на соседнем PR предлагал «переиспользовать» этот pattern.
- **Тот же день:** commit [`d7aab0e`](https://github.com/tenstorrent/tt-metal/commit/d7aab0e40c414735a2a8a8604d3a2a0f5d05f8ca) - `union` → `std::bit_cast<uint32_t>(eps)`. **Факт.**
- Автор пишет, что codebase search нашёл **много** `union {` - то есть не ограничился локальным fix, а пошёл смотреть шире. **Записано.**
- `rmillerTT`: «convert away from this UB **everywhere**». **Записано.**  
  https://github.com/tenstorrent/tt-metal/pull/33725#discussion_r2590254836

**Почему это team play, а не «починил замечание и забыл»:**

1. Принял стандартный аргумент без спора.
2. Исправил same-day.
3. Самостоятельно расширил поиск по репозиторию.
4. Lead зафиксировал codebase-wide ожидание - то есть вопрос уже не «строка в одном PR».

### 1.3 Approvals и просьба merge

- **2025-12-05:** автор просит нажать merge при green CI. **Записано.**
- Approvals: `bbradelTT`, `aliaksei-sala`, `vtsilytskyiTT`, maintainer `ayerofieiev-tt`. **Факт.**

### 1.4 Hold ради models `#31702`

- **2025-12-10:** комментарий автора: получил просьбу от Vash (`vsureshTT`) **придержать** merge, потому что models team спешит с `#31702`, которое сломается с этой infra-сменой. **Записано.**  
  https://github.com/tenstorrent/tt-metal/pull/33725#issuecomment-3637602359
- Автор **придержал**, хотя PR уже был approved. Это координация, не блокировка со стороны автора.

### 1.5 Hang жил в models Welford, не в `#33725`

- `#31702` (Welford / distributed layernorm) смёржен, затем [#34435](https://github.com/tenstorrent/tt-metal/pull/34435) откатывает его из-за hang в Llama3.3-70b prefill (локальный bisect в тексте revert PR). **Факт.**
- **2025-12-15-16:** автор откатывает временный rebase под models, затем **сам** ребейзит после `#34435` и перезапускает checks. **Записано** (комменты `3656841671`, `3661476335`).
- **2025-12-17:** `#33725` смёржен (`31d6c64`). **Факт.**

Календарный зазор ready→merge ≈ 14 дней, из которых hold/rebase под models - документированная часть.

---

## 2. Bundled 3-in-1: `#35146` под Новый год

### 2.1 Что видит скиммер

Title `#35146` ≈ «Fixes hang in layernorm distributed PR `#31702`» + op migration для pre/post allgather под Welford.  
Беглый взгляд: «hang + имя функции вокруг layernorm distributed» → легко повесить вину на недавнюю миграцию `#33725`.

### 2.2 Что на самом деле в PR (факт)

Один PR (≈46 files, merge **2026-01-02** `f27c718` by `vsureshTT`) совмещает как минимум:

1. **Revert** смёрженного `#33725` (commits вида `f8ee62c` / squash history).
2. **Revert-of-revert / re-land** Welford path из линии `#31702`.
3. **Redo** migration pre/post allgather уже models-owned layout’ом.

PR body: redo migration «to allow Welford's kernel to be merged in smoothly». **Записано.**

### 2.3 Процессная аномалия

- На треде `#33725` после merge **нет** human-комментария «мы откатываем твой PR потому что …». Последний human comment автора - rebase note **2025-12-16**. Дальше - referenced events. **Факт (архив комментариев).**
- Merge `#35146` - **02.01.2026**, праздничное/отпускное окно (контекст first-party; точные календарные отпуска людей - не доказываем здесь).

### 2.4 Асимметрия remediation (parallel case)

- Internal pre-migration `#33526` → dedicated revert `97f78f1` → retry `#34528` тем же автором. **Факт.**
- External post-migration `#33725` → bundled revert внутри `#35146` → redo другим автором, без notice на исходном PR. **Факт.**

H0: monorepo integration shortcut + ownership Welford у models. Не доказательство targeting.

---

## 3. UB: selective enforcement и возврат pattern

| Ось | External `#33725` | Internal `#31702` / `#35146` |
| --- | --- | --- |
| Flag | Сразу + cite стандарта | На `#31702`: «subsequent PR?» |
| Fix | Same-day `bit_cast` | `#31702` merged с union helper |
| После | Fix откатан в `#35146` | Host union + kernel `_bit_cast_` снова на merge `#35146` |
| Review talk про UB в `#35146` | - | **ноль** human hits (поиск по archive) |

Recurring idiom у того же автора: `#20212`, `#30029`, `#31702`, `#35146`. **Факт паттернов.**  
Intent «специально подставляли external» - **открыто / не утверждаем**.

Compiler note (чтобы не overclaim HW bug): ISO C++ - UB; sfpi GCC может трактовать union punning как extension. Сильный тезис здесь - **процесс** (откат documented host fix без обсуждения), не «доказанный мискомпил на устройстве».

---

## 4. Массовые op-registration refactors и provenance

**Наблюдаемый механизм (факт path churn):**

- `#35146` **удаляет** TMP subtree `#33725` (`layernorm_post_all_gather/…`) и пересоздаёт factory по другому пути.
- Параллельно в проекте шла волна TMP-миграций многих ops (в т.ч. серия merged PR автора + массовые миграции других людей; tooling/Cursor commands лида - **first-party** контекст процесса ревью, не GitHub-доказательство злого умысла).
- Фокус ревью на такой волне часто: соответствие новому registration style, `&` / `const`, не потерять логирование - а не глубокий audit каждого historical type-pun.

**Эффект для будущего `git blame`:** строки на текущих путях легко атрибутируются авторам redo/поздних правок, а не автору `#33725` / `d7aab0e`. Это **механизм потери provenance**, не доказанный заговор «спрятать UB за разными людьми».

Flaky red/green тесты как *следствие* этих UB - **открыто / first-party anecdote**; для `#33725` нет same-SHA green↔red артефакта в этом пакете.

---

## 5. Открытые вопросы (request for review)

1. Был ли полный revert `#33725` **технически необходим**, или Welford можно было rebase на TMP?
2. Почему на `#33725` не было post-merge notice автору?
3. Есть ли единая политика: host требует `std::bit_cast`, kernel допускает GCC union - и применяется ли она одинаково?
4. Почему «everywhere» на `#33725` не сопровождалось блокировкой того же pattern на `#31702` / `#35146`?

---

## Исключено из публикации

Private LinkedIn/Slack, сырые forensic dumps, обвинения в умысле как факт, аудио `20-22`/`0144` (нерелевантны), неперепроверенные ASR-детали.
