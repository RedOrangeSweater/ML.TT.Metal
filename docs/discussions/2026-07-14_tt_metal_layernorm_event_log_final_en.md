# Event log: silent bundled revert of merged TMP migration `#33725`, and union type-punning UB handling

**Repo:** personal fork discussion mirror of public `tenstorrent/tt-metal` history  
**Style:** FRAME-2 — observable public GitHub facts + open hypotheses. No motive asserted as fact.

---

## 60-second summary

I landed an approved TMP infrastructure migration for distributed LayerNorm post-all-gather ([#33725](https://github.com/tenstorrent/tt-metal/pull/33725), merged **2025-12-17**). Before merge I **held the PR on request** so the models team could land Welford work ([#31702](https://github.com/tenstorrent/tt-metal/pull/31702)), then **rebased myself** after that work was hang-reverted ([#34435](https://github.com/tenstorrent/tt-metal/pull/34435)).

Sixteen days later, a 46-file New-Year integration PR ([#35146](https://github.com/tenstorrent/tt-metal/pull/35146), merged **2026-01-02**) titled around fixing a hang in **`#31702`** also **reverted `#33725`**, re-landed Welford, and redid the migration — **without an explanatory comment on the `#33725` thread**.

Separately: a reviewer flagged union type-punning as UB on `#33725`; I fixed it the same day with `std::bit_cast` and searched the tree for more copies; a lead asked to remove the pattern “everywhere”. `#35146` reintroduced union packing on the merge commit, with **no human UB discussion** on that PR — while a similar helper on `#31702` had been deferred to a “subsequent PR”.

---

## 1. Team play on `#33725` (detailed)

### 1.1 Scope

- **2025-12-03:** opened [#33725](https://github.com/tenstorrent/tt-metal/pull/33725) — migrate `layernorm_post_all_gather` to the TMP device-op infra per `DEVICE_OPERATION_MIGRATION_GUIDE.md` (ticket `#32693`). Structural migration / registered prim — **not** the Welford algorithm and **not** the Llama hang fix.

### 1.2 Reviewer finds UB — author response

1. **2025-12-04** — `vtsilytskyiTT` flags union type-punning as undefined behavior and cites C++ §9.5 Unions:  
   https://github.com/tenstorrent/tt-metal/pull/33725#discussion_r2589099451
2. I acknowledged the historical blame lineage (the pattern predated the migration) and fixed it **the same day**:  
   [`d7aab0e`](https://github.com/tenstorrent/tt-metal/commit/d7aab0e40c414735a2a8a8604d3a2a0f5d05f8ca) — replace `union { float f; uint32_t u; }` with `std::bit_cast<uint32_t>(…)`.
3. I reported a codebase search finding **many** other `union {` sites — i.e. I did not stop at the single flagged line.
4. `rmillerTT` asked to convert away from this UB **everywhere**:  
   https://github.com/tenstorrent/tt-metal/pull/33725#discussion_r2590254836

That sequence is the team-play part: accept the standard cite, fix same-day, widen the search, and surface a repo-wide cleanup expectation.

### 1.3 Approvals and merge request

- **2025-12-05:** asked to press merge with green checks.
- Approvals included `bbradelTT`, `aliaksei-sala`, `vtsilytskyiTT`, and maintainer `ayerofieiev-tt`.

### 1.4 Hold for models `#31702`, then proactive rebase

- **2025-12-10:** I documented that `vsureshTT` asked me to **hold merge** because models were rushing `#31702`, which would break against this infra change:  
  https://github.com/tenstorrent/tt-metal/pull/33725#issuecomment-3637602359  
  I held an already-approved PR.
- `#31702` merged, then [#34435](https://github.com/tenstorrent/tt-metal/pull/34435) reverted it due to a hang in Llama3.3-70b prefill (stated in the revert PR; locally bisected there).
- **2025-12-15–16:** I undid the temporary models rebase, then **rebased onto main after `#34435`** and re-ran checks:  
  https://github.com/tenstorrent/tt-metal/pull/33725#issuecomment-3661476335
- **2025-12-17:** `#33725` merged as [`31d6c64`](https://github.com/tenstorrent/tt-metal/commit/31d6c645c21f49ed1bb972e4315fda5e55e776fe).

Hang ownership in the public record points at the **models Welford stream** (`#31702` / `#34435`), not at the TMP migration.

---

## 2. The bundled 3-in-1 New-Year PR `#35146`

### What a skimmer sees

`#35146` is titled around **fixing a hang in `#31702`** and also “including” op migration for pre/post all-gather under Welford. A casual history skim can read: hang near distributed layernorm → somehow related to the recent migration PR that touched the same op family.

### What the PR actually bundled (public facts)

[#35146](https://github.com/tenstorrent/tt-metal/pull/35146) (~**46 files**, merged **2026-01-02** as [`f27c718`](https://github.com/tenstorrent/tt-metal/commit/f27c718bd2474a33cee1e107dec618e72685ef39) by `vsureshTT`) combines at least:

1. **Revert** of merged `#33725`.
2. **Re-land** of the Welford / `#31702` line (revert-of-revert style history).
3. **Redo** of the pre/post all-gather migration under a consolidated layout.

Body rationale (paraphrase of public text): redo the op migration so Welford’s kernel can merge smoothly.

### Process gap

- There is **no** post-merge human comment on `#33725` explaining the revert to the author. Human issue comments on `#33725` stop at the **2025-12-16** rebase note; later activity is reference events.
- Timing: merge on **2026-01-02** — holiday / vacation window for many teams (calendar exports are not attached here; treat holiday staffing as context, not as a proven motive).

### Parallel remediation asymmetry

| Migration | Remediation |
| --- | --- |
| Internal pre `#33526` | Dedicated revert `97f78f1`, then author retry `#34528` |
| External post `#33725` | Bundled revert inside `#35146`; redo by another author; no notice on original thread |

**H0 (open):** monorepo integration shortcut + models ownership of Welford. Not proof of targeting.

---

## 3. UB pattern: strict on `#33725`, deferred / reintroduced elsewhere

| Axis | External `#33725` | Internal `#31702` / `#35146` |
| --- | --- | --- |
| Flag | Immediate + standard cite | On `#31702`: maybe fix in a “subsequent PR”? |
| Fix | Same-day `std::bit_cast` | `#31702` merged with union `_bit_cast_` helper |
| Aftermath | Host `bit_cast` fix reverted at `#35146` merge | Host `union` eps packing + kernel `_bit_cast_` union helper present at merge |
| Human UB talk on `#35146` | — | **None** found in public review/issue comments |

The same union idiom also appears in earlier merged normalization work by the same author (`#20212`, `#30029`, …).

**Compiler caution (do not overclaim hardware bug):** ISO C++ treats inactive-member reads as UB; sfpi/GCC may document union type-punning as an extension for kernels. The strong public claim here is **process**: a documented host fix was silently rolled back inside a giant PR with no UB policy discussion.

**Open:** whether flaky red/green tests were caused by this class of UB. That is anecdote / hypothesis without a same-SHA failure artifact attached to `#33725` in this package.

---

## 4. Mass op-registration refactors and blame provenance

**Observable mechanism:**

- `#35146` **deletes** the TMP subtree introduced by `#33725` and recreates factories on a different path.
- The project was in a broad wave of TMP / registration-style migrations across many ops. Review attention on such waves typically focuses on registration shape, accidental `&` / `const`, and preserving important logging — not a deep historical audit of every type-pun.

**Effect:** naive `git blame` on current paths naturally attributes lines to later redo authors. That is a provenance-loss **mechanism**, not evidence of a plan to hide UB behind many different people.

---

## 5. Requests for engineering review

1. Was a full revert of merged `#33725` **technically required**, or could Welford have rebased onto the TMP layout?
2. Why was there no explanatory comment on `#33725` when it was reverted?
3. Is there one written policy for union type-punning on **host** vs **sfpi kernel**, applied consistently?
4. How should “convert away everywhere” coexist with deferral on `#31702` and silent reintroduction on `#35146`?

---

## Public links

| Item | URL |
| --- | --- |
| `#33725` | https://github.com/tenstorrent/tt-metal/pull/33725 |
| Hold comment | https://github.com/tenstorrent/tt-metal/pull/33725#issuecomment-3637602359 |
| UB review | https://github.com/tenstorrent/tt-metal/pull/33725#discussion_r2589099451 |
| “Everywhere” | https://github.com/tenstorrent/tt-metal/pull/33725#discussion_r2590254836 |
| UB fix commit | https://github.com/tenstorrent/tt-metal/commit/d7aab0e40c414735a2a8a8604d3a2a0f5d05f8ca |
| `#33725` merge | https://github.com/tenstorrent/tt-metal/commit/31d6c645c21f49ed1bb972e4315fda5e55e776fe |
| `#31702` | https://github.com/tenstorrent/tt-metal/pull/31702 |
| `#34435` | https://github.com/tenstorrent/tt-metal/pull/34435 |
| `#35146` | https://github.com/tenstorrent/tt-metal/pull/35146 |
| `#35146` merge | https://github.com/tenstorrent/tt-metal/commit/f27c718bd2474a33cee1e107dec618e72685ef39 |

---

## Explicitly not claimed here

- Intent / sabotage / “targeting” as fact.
- That `#33725` caused the Llama hang.
- That union punning is a proven device miscompile without a reproducer.
- Private LinkedIn/Slack/calendar contents (screenshots not attached).
