## /game.extract — вынести игру в отдельный репо (движок в REU)

Движок в REU; игра — отдельный репо под `/home/kilka/Projects/Games/<GameName>/`. Игра = config + assets; в REU — краткий reference. Трекинг в cursorrules.

### Input

Обязательно: `gameName` (напр. MaxComfy). Опционально: `targetPath`, «что оставить в REU».

### Алгоритм

- Создать `/home/kilka/Projects/Games/<GameName>/`, `git init`, scaffold (README, package manager, src/, docs/, game config).
- **Initial commit обязателен** до добавления remote.
- Разделить код/артефакты: движок остаётся в REU, игра — в новом репо.
- В REU: reference (без «истины» по дизайну/механикам).
- В cursorrules: `docs/projects/<project-slug>/` + templates + upstream snapshot.

### Output / Constraints

Чеклист по шагам; atomic commits; пуш только по запросу.
