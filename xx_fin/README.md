# XXFIN 
## About
The xxfin package of the 10x project serves a dual purpose:

- to illustrate the capabilities of the 10x system by implementing a sufficiently rich example solving an important
  problem in an important subject domain
- to provide a complete working implementation of the most foundational valuation problem in the financial domain:
  calculating today's price of a fixed amount of a future cash flow denominated in any currency.

To achieve this goal, one needs to determine the relevant currency/foreign exchange (FX) rates and discount factors in a
manner consistent with the current market data. Hence, we define all the necessary data structures for market data,
including:

- an ingestion/translation facility for collecting market data from any chosen data providers
- generation/population/storage objects for standard quoted market data
- models for calibrating complex/"synthetic" objects (forward curves), allowing calculation of rates/values that are not
  directly observable but are consistent with all the relevant markets

The sequence of the valuation steps is as follows:

- We create market data objects ("quotables") that contain the market quotes and are stored in a user-specified market
  data store.
- The user specifies an external market data provider.
- An adapter is needed to translate the market data from the provider's format and populate our quotables.
  - We may provide such an adapter for a commonly used provider (e.g., Bloomberg), and, at a later date, add more
    adapters if demand warrants it.
  - We create a sample set of quotables which allow us to illustrate the use of market data.
- Each piece of market data is quoted as a number (or a collection of numbers) representing values/parameters of certain
  standard financial contracts, and the set of specifications sufficient to describe and value such standardized
  contracts is saved in "market convention" objects.

The subset of all market quotables used to build/calibrate synthetic market data (forward curves) is called a market
assembly. It usually consists of the most liquid contracts that provide the most precise view of market participants on
the market (e.g., the most liquid swap or FX forward quotes). Once we ingest the market quotes from the data provider(s)
into the quotables, we use a market assembly to build/calibrate the forward curve using a chosen calibration procedure.
The subsequent use of the curves built this way is completely agnostic to the curve calibration choices. Hence, the
market assembly, as well as the calibration analytics, can be replaced by the user's preferred choices.

The discount curve for a discount rate in a given currency is built using that currency-denominated standard cash
deposit and fixed-floating swap market quotes, with that rate as the underlying/reference floating rate for the
instruments listed in a market assembly (e.g., for the SOFR curve we use USD cash deposits and SOFR standard annual
fixed/floating swap quotes).

For FX forward curve construction, we currently use FX spot and FX forward (point) quotes for rates
funded/collateralized in the same currency (e.g., USD). We build an FX curve for a market assembly-specified set of FX
spot and FX USD-collateralized forwards consistent with the funding currency's discount curve.

Such an FX forward curve allows us to calculate the present value, in any given currency, of a cash flow denominated in
any other currency.

## Optional JIT acceleration via AADC

`xxfin/jit_aadc/` optionally records curve/valuation code into a JIT-compiled adjoint
differentiation kernel using [MatLogica's AADC](https://pypi.org/project/aadc/) (Adjoint Algorithmic
Differentiation Compiler), enabled via the `use_cxxfin`/`aadc_license` settings in
`xxfin_env_vars.py`. `aadc` installs freely from PyPI and is a required dependency on non-macOS platforms; it's excluded
on macOS because MatLogica doesn't publish an aadc build for that platform. It ships with a
time-limited trial license out of the box, but continued or production use requires a license key
obtained from MatLogica. `xxfin` itself
works fully without it — AADC only accelerates the JIT-compiled code path.

## An easy setup to start playing with xxfin package
- install mongodb on your machine and run without authentication (default)
- set environment variables:
  - XX_MAIN_TS_STORE_URI=mongodb://localhost/xx_fin (or any other MongoDb)
  - XXFIN_DEFAULT_PRICING_CONTEXT_NAME=Abu Dhabi 20251010
- run xxfin/dev_data_helpers/RUN_ME.py (it will store a number of objects)
- you are ready to go!