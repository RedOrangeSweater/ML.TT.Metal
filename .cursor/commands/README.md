# Canonical .cursor/commands (shared across portfolio)

Shared slash-commands set for portfolio projects. Source: RulesEngineUniverse workflow (commands-first: curs.*, sdlc.*, hat.*, release.aaa, game.extract).

- **Propagation**: `tools/propagate_cursor_rules_to_upstreams.py` copies this folder to each upstream `.cursor/commands`.
- **Update**: When REU or another project improves commands, snapshot into `docs/projects/<project>/commands.upstream-*`, then copy the chosen set here and re-run propagation.
