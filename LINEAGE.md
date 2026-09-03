# The Reusable 80%

### What 10x Genaxy Is — and Isn't

_By Sasha Davidovich, with Ilya Pevzner and Alex Lesin_

This is a paper about what 10x Genaxy is. It starts, oddly, with a story from years before it existed — because the clearest way to explain what it is now turns out to run through a question I couldn't answer well back then.

## What Is Athena?

In 2011, shortly after joining JPMorgan to lead its Athena platform, I stood in front of a room of senior executives for my introduction. Athena had been running for about five years by then, built by a group of colleagues who had since left for another bank, and the firm had already spent a great deal of money on it. Someone in the room asked a question I hadn't prepared for:

_"What is Athena?"_

I had about two minutes, in a room with almost no shared technical background, to explain something that had taken years and enormous effort to build. Whatever I said, most of it wasn't going to land — the real answer was too tangled up in implementation detail for a live introduction. So I reached for the one piece of technology everyone in the room already understood.

"You all know what an operating system is," I said. "Windows on your PC. macOS on your Mac. iOS on your phone." Nods — of course they knew.

"Had a special-purpose computer existed for a financial institution like JPMorgan, Athena would have been its operating system."

The room lit up — though probably not because the explanation had gotten any simpler. Nobody in that room could really explain what an operating system does either; they just knew Windows, macOS, and iOS by name and by feel, from using them every day. Somehow, anchoring Athena to something equally unexplained but comfortably familiar was enough. For a moment, the room felt it finally understood what Athena was.

It was true then, and it's truer now — except this time, the thing I'm describing isn't proprietary, isn't buried inside one bank, and isn't limited to one industry.

## The Pattern That Keeps Getting Rebuilt

That question in 2011 wasn't the first time I'd lived inside this pattern. Years earlier, at Goldman Sachs, I'd worked within the lineage that everything after it — including Athena — descended from: a system called SecDb, built starting in the mid-1990s, where every instrument, trade, and risk calculation lived as a node in a dependency graph, computed lazily and shared globally across every desk in the firm.

The idea proved durable enough that it kept getting rebuilt — largely by the same lineage of people — at other institutions. JPMorgan built Athena starting in 2006. Bank of America built Quartz starting in 2010. In 2014, a version was spun out entirely as an independent platform company: Beacon.

Four systems, spanning roughly twenty years. Three banks and one standalone company. The same core idea, rebuilt from scratch each time, because none of it was portable — nothing generalized past the walls of a single employer. Even the people who understood this pattern best had to start over every time they changed jobs.

That repetition is the argument for 10x Genaxy. If the same architects rebuilt the same 80% of a platform three or four times over twenty years, the 80% deserves to exist on its own — outside any one bank, and outside finance altogether.

The story above is personal, because it happened to me before 10x Genaxy existed. 10x Genaxy itself is not: it's being built by a small team, not by one person alone.

## What 10x Genaxy Is

**10x** is about empowering engineers, researchers, and developers to become 10x more productive — not through better tooling at the edges, but by never rebuilding the same foundation twice. A **genaxy** is the kind of system that makes that possible — a **generative** core with subject domains built on top of it, rather than a domain application that reinvents the core.

**Generative** means the running system is derived from a description of the entities rather than assembled feature by feature. You say what an entity is, what it depends on, where it is stored, and how it should be presented. From that description the rest follows.

That core is the **substratum**: a small set of laws (the underlying principles) from which the rest of the system is derived. Subject domains surround it the way planets surround a star — independent, distinct, but held by the same laws. SecDb, Athena, Quartz, and Beacon were genaxies; each had a substratum, and none could leave the building.

**10x Genaxy** is this genaxy. Its substratum is the reusable 80% every industry-specific platform ends up building — identity, dependency tracking, persistence, and presentation — so a team only has to build the 20% that's actually theirs.

Concretely: `py10x-core` (the substratum) is a domain-agnostic Python framework built around a single idea — objects with deterministic identity (`Traitable`s), organized in a dependency graph that computes lazily and updates automatically, persisted transparently to whatever storage a team already runs. Finance is the first domain built on top of it (`py10x-fin-base`), but nothing about the core is finance-specific. Any subject domain with derived state and shared entities can build on the same foundation instead of reinventing it.

If you want a CS reference point rather than an anecdote: the closest existing pattern is Entity-Component-System (ECS) architecture from game engines ([Bilas, GDC 2002](https://www.gamedevs.org/uploads/data-driven-game-object-system.pdf)) — identity-bearing entities, decoupled data, systems that compute derived state. 10x Genaxy follows the same shape, extended with the pieces ECS was never asked to provide, because games don't need to survive a database restart or generate their own admin console: persistence, a full dependency graph, and automatic UI generation.

## Four Pillars

**1. Identity, Dependency Graph, Persistence.** A `Traitable` has deterministic identity: two instances with the same identity traits _are_ the same logical object, sharing state through a global cache. Derived fields are computed lazily, on first access, with dependencies tracked automatically — change an input, and everything downstream recomputes itself with no manual invalidation code. The whole graph persists transparently through a pluggable Traitable Store, with built-in versioning and history.

**2. Two Kinds of Graph: Lazy and Reactive.** SecDb's dependency graph answers "what is this value, computed on demand." There's an orthogonal problem it was never built for: data that arrives and has to propagate _forward_ — market ticks, events, real-time trading signals. I built a forward-propagating version of that idea alongside the lazy graph, at both Goldman Sachs and JPMorgan. It never made it into Quartz or Beacon. A related open-source project, `csp`, released independently by its maintainers, implements a similar reactive-dataflow model and is used in production today for real-time and algorithmic trading — it sits in the same lineage of ideas, and we consider it a friendly, complementary project rather than a competitor. Separately, `py10x-core` now ships its own event-processing capability — a third, distinct implementation of the reactive idea, not derived from either of the earlier ones.

**3. Infrastructure Without the Boilerplate.** Every external dependency — a database, a cluster, anything — is a `Resource`, addressed by URI and resolved to a concrete driver registered under a `ResourceType`. Traitable Store is just one instance of this pattern: drivers exist today for MongoDB, PostgreSQL, and DuckDB, and because the Postgres/DuckDB drivers sit on top of Ibis, the backend catalog is architecturally open to anything Ibis already supports. Authentication is handled the same way, once, for everyone: a vault-backed system generates an RSA keypair on the user's own machine, encrypts the private key with their own master password, and stores everything in the OS keyring — credentials never cross the wire. One registration step grants a user access to every resource on that vault server, with no manual per-database credential wiring.

**4. UI That Writes Itself.** A `Traitable` subclass with typed fields is enough to generate a full, working editor — dropdowns, checkboxes, grouped layout, a live preview — with no manual UI code at all. In one real example (`ui_10x/examples/style_sheet.py`), a ~35-line class produces a complete style editor whose preview pane updates live as you change colors, fonts, and borders — because the preview is just another computed trait in the same dependency graph. The dropdowns need no configuration at all: typing a trait as a `NamedConstant` subclass (e.g. a `COLOR` enum) is enough for the framework to pick a choice widget and populate its options automatically — no `ui_hint` or choice-list method required. `ui_hint` annotations are only needed where a default needs a nudge — a label, a grouping separator. The same class definition renders as a native Qt desktop dialog or a Rio web view, depending only on which backend is active.

<img src="Screenshot_style_sheet.jpg" alt="The entire StyleSheet trait class (left) and the auto-generated editor it produces (right) — the WYSIWYG preview updates live from the dependency graph, with no manual UI code anywhere." width="1000">

## What 10x Genaxy Is Not

- Not a business-intelligence tool or dashboard builder.
- Not an ORM — identity isn't tied to a database row, and persistence is optional and pluggable.
- Not a finance-specific platform — finance is the first domain pack, not the point of the project.
- Not a competitor to reactive/streaming frameworks like `csp` — complementary, solving an adjacent problem.
- Not tied to one storage technology — MongoDB, PostgreSQL, and DuckDB today, more by design.

## Closing

That question in 2011 — "What is Athena?" — never really had a good two-minute answer, because the honest answer was tangled up in one bank's internal history, understood fully by almost no one outside the small group who built it, and had no name you could take outside the building.

10x Genaxy is an attempt to give a better answer this time: not a platform owned by one institution, rebuilt from scratch by whoever happens to inherit it next, but a shared, open foundation that any domain — finance included — can build on and actually keep.

---

_py10x-core and py10x-fin-base are open source. [github.com/10x-software/py10x](https://github.com/10x-software/py10x)_
