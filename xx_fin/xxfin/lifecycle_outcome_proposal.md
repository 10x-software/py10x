# `LifecycleOutcome` — design proposal (not yet applied)

Status: **proposal only**. Nothing in this document has been implemented. `FinInstrument.lifecycle_transform()`
today still returns `FinBasket | XNone` (see `fin_instrument.py`). This note captures the settled shape of an
extension to that contract, worked out 2026-10-08, so the reasoning and rejected alternatives aren't lost.

## Motivation

`lifecycle_transform()`'s current contract (`-> FinBasket`, or `XNone` if nothing fires) can only say "here's what
it became." Two real cases need more than that:

- **Option-exercise-like events** that may not be fully automatic — some need a human/counterparty decision
  (an election) before anything should actually be applied.
- **Market-data-conditional firings** (barrier breaches, exercises, etc.) where a human reading the result later
  wants to know *why* it fired, not just what it became.

Both point at the same gap: the "fired" case needs to carry more than a bare `FinBasket`.

## The class

Defined in `fin_instrument.py`, right after `FinBasket` and before `FinInstrument` (no circularity — it only
needs `FinBasket`, not `FinInstrument`):

```python
class LifecycleOutcome(FinBasket, embeddable = False, custom_collection = True):
    instrument: FinInstrument = T(T.ID)
    reason: dict               = T()      #-- free-form, human-readable, formed by whichever instrument fired
    automatic: bool            = T(True)   #-- False: a decision is pending; basket may be XNone until resolved
```

`lifecycle_transform()`'s contract becomes:

```python
def lifecycle_transform(self) -> LifecycleOutcome | None:
    ...
```

`None` here is the plain Python sentinel, not the framework's `XNone` — this is an ordinary function return, not a
trait read, so there's no "unset trait" semantics to borrow.

### Why `LifecycleOutcome(FinBasket, ...)` — inheritance, not a wrapper field

`LifecycleOutcome` *is* a `FinBasket` rather than wrapping one in a `.basket` field. This means every existing
caller that currently treats the "fired" result as a basket (`.members_qtys()`, `Lifecycler`'s
`basket.the_bucket.members_qtys()`, `FinBasket.fire_lifecycle()`) keeps working unchanged against a
`LifecycleOutcome` instance — the only addition is callers *can* also read `.reason`/`.automatic` if they care to.
`Basket.of()` works too: `LifecycleOutcome.of((cash, qty), reason = {...}, automatic = False)`.

### Why `embeddable = False`

`FinBasket` is itself `embeddable` (inherited from `Basket(Traitable, embeddable = True)` in `core_10x/basket.py`),
and `Traitable.__init_subclass__` makes `s_embeddable` inherit unless a subclass explicitly overrides it. Left
alone, `LifecycleOutcome` would silently inherit `embeddable = True` — which would make it *only* ever storable
embedded inside another Traitable's data, never as a standalone record. Since non-automatic outcomes need to be
independently inspectable by a human, it must be able to stand on its own: `embeddable = False` is required, not
optional, despite inheriting from an embeddable base. (Checked: nothing in `traitable.py` blocks "un-embedding" a
subclass of an embeddable base — the only guard runs the other direction, embeddable classes may not have `T.ID`
traits, which doesn't apply here.)

### Why no `code`/kind field, and no `LifecycleReason` subclass hierarchy

Earlier iterations of this design tried:
- A `code: LIFECYCLE_REASON` trait (a `NamedConstant`) — dropped once `reason` became a free dict, since there's
  no longer a fixed vocabulary to classify against.
- A `LifecycleReason` Traitable base with one subclass per reason kind (`BarrierBreachReason`, `OptionExerciseReason`,
  ...), each with its own typed fields (`spot`, `barrier`, `strike`, `payoff`...) — mirroring how `Bucketizer` has
  one subclass per matching strategy. Rejected: real firing conditions vary too much per instrument to usefully
  close the vocabulary; it would turn into one subclass per instrument type with little shared structure, for a
  field whose real job is "explain yourself to a human reading it later," not drive typed logic elsewhere.
- A `target_trait: str` (naming the instrument's own trait holding the threshold, e.g. `'barrier'`) + a reference
  to the triggering market-data object(s) — elegant in theory (avoids ever duplicating the threshold value,
  since it's just a pointer back to `getattr(instrument, target_trait)`), but still needs the per-kind data problem
  solved for the market-data side, and adds a layer of indirection for a field whose job is readability.

Settled on: `reason: dict = T()`, free-form, with whichever instrument fires deciding what's worth reporting
(e.g. `{'spot': 105.2, 'barrier': 100.0}`). Consistent with "`FinInstrument` decides" — the shape of the
explanation is the firing instrument's call, not something a shared framework class should constrain.

### Why no `pricing_context` trait

`lifecycle_transform()`'s result is a pure function of `(self, PricingContext.current())` — already true per its
existing docstring. An earlier version of this design added `pricing_context: PricingContext = T(T.ID)` alongside
`instrument`, specifically so that re-evaluating the same instrument under a *different* pricing context (a
different day) would get a distinct, non-clobbering identity rather than overwriting the previous day's outcome
on a shared object.

That's now handled by storage partitioning instead (see below) — a Traitable's `collection_name` is a first-class
part of its `TID` (`ID(collection_name=..., value=...)`), so once outcomes are partitioned into one collection per
`(context-type, date)`, `instrument` alone is sufficient as the ID *within* a given collection, and two outcomes
for the same instrument on different days are automatically distinct because they live in different collections.
Storing `pricing_context` as a trait too would just be duplicating information the collection path already
encodes.

## Storage

**Scope note**: only this file's class shape is being designed. What actually calls `.save()` on a
`LifecycleOutcome`, and when, is a `Lifecycler`/`positions_lineage` decision — explicitly out of scope for this
proposal (see `project-fininstrument-lifecycle-api` memory for that boundary).

**In-memory vs. durable, kept separate.** Identity-sharing in memory (within one evaluation run's cache scope) is
not the concern — it's bounded by the run and reclaimed by ordinary cache/GC lifetime once that scope ends, the
same as any other Traitable created inside a short-lived cache context. The real growth risk is *persisting*
every outcome, for every instrument, for every day, forever.

**Resolution**: only `automatic = False` outcomes are expected to actually get persisted — the ones a human needs
to see and act on. That's a naturally small, bounded set (genuinely pending decisions), not "every instrument
every day." This is a calling-convention decision at the call site (`if not outcome.automatic: outcome.save()`),
not something `LifecycleOutcome` enforces itself — it stays a plain value.

**Collection partitioning**, to keep even that persisted set from becoming one single ever-growing collection:

```python
pc = PricingContext.current()
coll_name = f'{PyClass.name(LifecycleOutcome)}/{pc.mkt_data_provider_name}/{pc.snapshot.name}/{pc.md_date.isoformat()}'
outcome = LifecycleOutcome(instrument = inst, reason = {...}, automatic = ..., _collection_name = coll_name)
```

Four path segments: canonical class name (`PyClass.name(...)`, not a hand-typed string — stays correct through
any future rename via the same `PackageRefactoring`-aware machinery used elsewhere in `core_10x`) / market-data
provider / snapshot / evaluation date.

`<pricing_context_type>` deliberately = `mkt_data_provider_name` + `snapshot` only — **not** `pricing_mode`
(`PRICING` vs `MKT_RISK`). `pricing_mode` describes *why* a pricing run is happening, not *what market data* a
lifecycle firing decision depends on; the same `(provider, snapshot, date)` must produce the identical outcome
regardless of mode, so partitioning by mode would wrongly split what's actually the same determination.

`custom_collection = True` is required on the class for `_collection_name` to be an accepted constructor kwarg at
all (`core_10x/traitable.py:417`, `Traitable.__init_subclass__`) — without it, passing `_collection_name` raises.

## Open items — not yet decided

- **Resolution tracking**: once a human acts on a stored pending (`automatic = False`) outcome, does the same
  stored record get updated (so "pending" queries naturally exclude it once resolved), or does it stay untouched
  as a historical artifact with resolution tracked entirely elsewhere (e.g. as an ordinary trade/event in
  `positions_lineage`)? Affects whether `LifecycleOutcome` eventually needs something like `resolved: bool` — not
  decided.
- **Migration**: every existing `lifecycle_transform()` implementation (`CcyForward`, `CmAvgForward`,
  `CmStripSimple`, `MaturingNote` ×2, and the 7 fixtures in `xxfin_positions_lineage/unit_tests/test_positions_lineage.py`)
  currently returns a bare `FinBasket` and would need to wrap it as `LifecycleOutcome(...)` instead. Not started;
  explicitly deferred until this shape is confirmed.
- **`Lifecycler` consumption**: nothing in `positions_lineage.py` reads `.reason`/`.automatic` yet, and nothing
  decides what "pending, don't auto-apply" should actually mean operationally for the catch-up walk. Out of scope
  for this proposal by design.

See also: `project-fininstrument-lifecycle-api` and `feedback-correctness-by-construction` (Claude's own session
memory, not part of this codebase) for the broader lifecycle-API context this extends.
