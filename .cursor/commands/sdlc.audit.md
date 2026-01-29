## /sdlc.audit — аудит docs и SDLC-артефактов

Русский, структура без воды. Цель: согласованность навигации, SoT, статусов, спек, QA, run configs, Mermaid.

### Input

Опционально: путь к `TASK_*`, описание изменений (1–5 строк) или список путей. **Пусто** → полный layered audit (Direction → Status → Specs → QA → Runbooks → Cursor).

### Режимы

- **Без параметров**: слои 1–6 по порядку; каждый слой улучшай перед переходом к следующему.
- **С параметрами**: быстрый audit только по затронутым частям.

### Чеклист (по умолчанию)

- SoT + start here: `docs/README.md` → `docs/sdlc/00_Main/00_Status/00_projects_graph.md`.
- Статус: `00_projects_graph.md`, `01_Kanban.md` — валидны, без битых путей.
- Run configs: доки «как запускать» ↔ `.vscode/{launch.json,tasks.json}`.

### Output

- **SoT** + start here.
- **Changed surface**: 3–10 буллетов (что менялось).
- **Required SDLC updates**: Task context, BA, Arch, Testing, Status — или «не требуется».
- **Gaps / risks**: 1–5 пунктов.
- **Next actions**: 3–7 пунктов «сделай X в файле Y».

### Constraints

Фокус на согласованности; без широких рефакторов. Коммит/пуш — atomic workflow, без auto-push.
