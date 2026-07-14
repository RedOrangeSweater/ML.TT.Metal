# Evidence manifest - tt-metal layernorm revert / UB event log

**Branch:** `discussion/10-layernorm-revert.dev`  
**Target Discussion:** `shutovilyaep/tt-metal`  
**FRAME-2:** observable public GitHub facts + open hypotheses. No private DMs, no motive-as-fact.

## Claim levels

| Level | Meaning |
| --- | --- |
| **fact** | Public GitHub permalink / commit / path:line |
| **recorded** | Verbatim public PR/review comment |
| **first-party** | Author recollection (not independently exported here) |
| **open** | Hypothesis with falsifier; not asserted as settled |

## Public anchors

| Claim | Level | Anchor |
| --- | --- | --- |
| `#33725` opened 2025-12-03; TMP migration `layernorm_post_all_gather` | fact | https://github.com/tenstorrent/tt-metal/pull/33725 |
| Reviewer flagged union type-punning as UB (C++ §9.5) | recorded | https://github.com/tenstorrent/tt-metal/pull/33725#discussion_r2589099451 |
| Same-day fix `std::bit_cast` | fact | https://github.com/tenstorrent/tt-metal/commit/d7aab0e40c414735a2a8a8604d3a2a0f5d05f8ca |
| Lead asked convert away from UB “everywhere” | recorded | https://github.com/tenstorrent/tt-metal/pull/33725#discussion_r2590254836 |
| Author searched codebase for more `union {` | recorded | `#33725` review thread (2025-12-04) |
| Approvals including maintainer | fact | `#33725` reviews (`bbradelTT`, `aliaksei-sala`, `vtsilytskyiTT`, `ayerofieiev-tt`) |
| Hold merge for models `#31702` at `vsureshTT` request | recorded | https://github.com/tenstorrent/tt-metal/pull/33725#issuecomment-3637602359 |
| `#31702` merged with union `_bit_cast_` helper; defer comment | fact + recorded | https://github.com/tenstorrent/tt-metal/pull/31702 |
| `#34435` reverts `#31702` for Llama3.3-70b hang | fact | https://github.com/tenstorrent/tt-metal/pull/34435 |
| Author rebased after `#34435` | recorded | https://github.com/tenstorrent/tt-metal/pull/33725#issuecomment-3661476335 |
| `#33725` merged 2025-12-17 | fact | https://github.com/tenstorrent/tt-metal/commit/31d6c645c21f49ed1bb972e4315fda5e55e776fe |
| `#35146` merged 2026-01-02 (46 files): revert `#33725` + Welford redo + migration redo | fact | https://github.com/tenstorrent/tt-metal/pull/35146 ; merge `f27c718` |
| Hang framing names `#31702`, not `#33725` | fact | `#35146` title/body |
| No post-merge explanatory comment on `#33725` thread | fact | `#33725` issue comments end 2025-12-16 (human) |
| Host `bit_cast` fix reverted; union reintroduced at `#35146` merge | fact | merge tree of `f27c718` host program factory |
| Zero human union/UB discussion on `#35146` | fact | public review/issue comments search |
| Same union idiom in earlier `vsureshTT` norm PRs | fact | `#20212`, `#30029`, `#31702`, `#35146` |
| Internal `#33526` got dedicated revert + retry `#34528` | fact | commits `97f78f1`, `4330a3f` |
| Path delete of TMP subtree obscures naive blame | fact (mechanism) | `#35146` removes `layernorm_post_all_gather/` |
| Full revert was *technically required* | open | no public incompatibility design doc |
| Intentional targeting / concealment | open | no intent artifact |
| Flaky red/green CI caused by this UB class | open / first-party | not tied to a same-SHA failure artifact for `#33725` |

## Deliberately excluded from this package

- Private LinkedIn / Slack / calendar exports
- Raw JSON/HTML forensic dumps
- Absolute local paths under Personal archives
- Motive language as settled fact (“sabotage”, “диверсия”)
