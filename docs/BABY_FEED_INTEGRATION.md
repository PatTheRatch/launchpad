# Baby Feed Integration (Huckleberry)

> Status: **Proposed — not yet implemented.** This document is the hand-off spec
> for adding a live "last feed" section to the Launchpad dashboard.
>
> Author: AIsha · Date: 2026-08-17

## 1. Purpose

Show the baby's **most recent feed** and **time since that feed** on the e-ink
dashboard, replacing the (still-mock) calendar slot. The baby is a newborn, so
this section must be visible in every time-of-day mode.

Parents keep logging feeds in the **Huckleberry** app exactly as they do today;
Launchpad only *reads* the data. No logging workflow changes for Patrick or
Alexandra.

## 2. Current state (what already exists)

The codebase already anticipated this feature; the gaps are small and specific:

| Layer | File | Today | Needed |
|---|---|---|---|
| Model | `src/launchpad/models/experimental/baby.py` | generic `BabyEvent` + `BabySnapshot` | feed-specific model |
| Service | `src/launchpad/services/experimental/baby_service.py` | abstract `BabyService` stub | concrete `HuckleberryBabyService` |
| Wiring | `src/launchpad/factory.py` | `baby` **not wired** (defaults `None`) | wire the service |
| Layout | `src/launchpad/builder.py` | `Section.BABY` only in **evening** | add to all four modes |
| Render | `src/launchpad/rendering/portrait.py` | **no `BABY` handler** | add `_draw_baby` |
| Flag | `src/launchpad/config/features.py` | `baby_tracking: bool` exists | *(nothing — set env)* |
| Deps | `pyproject.toml` | — | `huckleberry-api==0.2.2` |
| Env | `.env` / `.env.example` | — | `HUCKLEBERRY_EMAIL` / `HUCKLEBERRY_PASSWORD` |

The service contract is `DataService[T]` with a **synchronous** `fetch() -> T`
that raises `ServiceError` on failure (see `services/base.py`).

## 3. Data flow

```
Huckleberry (Firebase backend)
        │  huckleberry-api 0.2.2  (email/password auth)
        ▼
HuckleberryBabyService.fetch()  ──►  BabySnapshot  (immutable model)
        │                                  │
        │  Result.unavailable() on failure  │
        ▼                                  ▼
Dashboard.collect()  ──►  DashboardStateBuilder.build()  ──►  SectionState(Section.BABY)
                                                                      │
                                                                      ▼
                                            PortraitRenderer._draw_baby()  ──►  e-ink
```

## 4. Data model

Replace the generic `BabyEvent` in `models/experimental/baby.py` with a
feed-specific model. `BabySnapshot.last_feed` becomes `Feed | None`.

```python
class FeedType(str, Enum):
    BREAST = "breast"    # direct nursing
    BOTTLE = "bottle"    # pumped breastmilk in a bottle
    FORMULA = "formula"  # formula in a bottle

@dataclass(frozen=True, slots=True)
class Feed:
    feed_type: FeedType
    started_at: datetime          # timezone-aware
    ended_at: datetime            # breast: start + durations; bottle: start
    amount_ml: float | None       # bottle/formula only
    side: str | None              # breast only ("left"/"right")
    duration_seconds: float | None  # breast only (left + right)
```

## 5. The `huckleberry-api` library

Unofficial Python client that talks to Huckleberry's Firebase backend using the
account email + password. Prior art / actively maintained: the
[`Woyken/huckleberry-homeassistant`](https://github.com/Woyken/huckleberry-homeassistant)
Home Assistant integration (built on the same library).

**Version pin — critical:**

| Version | `requires_python` |
|---|---|
| `0.2.2` and earlier | `>=3.9` ✅ |
| `0.2.3` → `0.4.3` | `>=3.14` ❌ |

Launchpad runs **Python 3.13.5** (system and venv). Pin **`huckleberry-api==0.2.2`**.
Do not upgrade past `0.2.2` until the Pi has Python 3.14.

Verified 2026-08-17: `0.2.2` authenticates and returns live data against the
current backend (smoke test succeeded — 72 feed intervals in 7 days).

### API surface used

```python
from huckleberry_api import HuckleberryAPI

api = HuckleberryAPI(
    email=..., password=..., timezone="Europe/London", websession=aiohttp_session
)
await api.authenticate()                     # Firebase signInWithPassword
user = await api.get_user()                  # .childList -> [ {cid}, ... ]
cid = user.childList[0].cid                  # single child for v1
feeds = await api.list_feed_intervals(cid, start_ts, end_ts)  # list of intervals
```

The library bundles Huckleberry's Firebase config internally (project
`simpleintervals`), so no Firebase credentials are needed beyond the account
login.

### Confirmed live data shape

**Bottle feed** (`mode="bottle"`):

```json
{
  "mode": "bottle",
  "start": 1786957800.0,
  "lastUpdated": 1786964348.503,
  "bottleType": "Formula",
  "amount": 80.0,
  "units": "ml",
  "offset": -60.0,
  "end_offset": null,
  "notes": null
}
```

**Breast feed** (`mode="breast"`):

```json
{
  "mode": "breast",
  "start": 1786881505.0,
  "lastSide": "right",
  "lastUpdated": 1786882151.132,
  "leftDuration": 0.0,
  "rightDuration": 360.0,
  "offset": -60.0,
  "end_offset": -60.0,
  "notes": null
}
```

`leftDuration` / `rightDuration` are in **seconds** (360 = 6 min).

## 6. Mapping logic (Huckleberry → Feed)

| `mode` | `bottleType` | `FeedType` | notes |
|---|---|---|---|
| `breast` | — | `BREAST` | `side = lastSide`, `duration = left+right` |
| `bottle` | `Formula` | `FORMULA` | `amount_ml = amount` |
| `bottle` | `Breast Milk` | `BOTTLE` | `amount_ml = amount` |
| `bottle` | *other* | `BOTTLE` | log the unknown type at debug |

- `ended_at` for **breast** = `start + leftDuration + rightDuration`.
- `ended_at` for **bottle** = `start` (parents log the bottle at finish, so
  `start` ≈ finished).
- **Units:** `units` can be `ml` or `oz`. Convert `oz → ml` (× 29.5735) so the
  display is always ml, or carry the unit through — decide during implementation.
  (Patrick's data is currently all `ml`.)

## 7. Service design

New `HuckleberryBabyService(BabyService)` in
`services/experimental/baby_service.py`:

```python
class HuckleberryBabyService(BabyService):
    def __init__(self, email, password, timezone="Europe/London", lookback_days=7):
        ...

    @property
    def name(self) -> str:
        return "huckleberry:baby"

    def fetch(self) -> BabySnapshot:
        return asyncio.run(self._fetch_async())

    async def _fetch_async(self) -> BabySnapshot:
        now = int(time.time())
        start = now - self._lookback_days * 86400
        async with aiohttp.ClientSession() as session:
            api = HuckleberryAPI(self._email, self._password, self._timezone, session)
            await api.authenticate()
            user = await api.get_user()
            if user is None or not user.childList:
                raise ServiceError("no child profile")
            cid = user.childList[0].cid
            feeds = await api.list_feed_intervals(cid, start, now)
            if not feeds:
                return BabySnapshot(last_feed=None, retrieved_at=datetime.now(LONDON))
            latest = max(feeds, key=lambda f: f.start)
            feed = _map_feed(latest)
            return BabySnapshot(last_feed=feed, retrieved_at=datetime.now(LONDON))
```

### Async bridge

The existing services are synchronous; `huckleberry-api` is async (`aiohttp`).
Bridge with `asyncio.run(...)` inside `fetch()`. A fresh event loop per refresh
is fine at the 5-minute cadence. Do **not** refactor the dashboard to async.

### Error handling

Every failure (auth, network, missing child, parse) becomes `ServiceError`, which
`Dashboard._fetch_result` already converts to `Result.unavailable()`. The section
renders a graceful placeholder — never a crash.

## 8. Factory wiring

In `factory.py`, add to the `ExperimentalServices(...)` construction:

```python
baby=HuckleberryBabyService(
    email=os.getenv("HUCKLEBERRY_EMAIL", ""),
    password=os.getenv("HUCKLEBERRY_PASSWORD", ""),
) if settings.features.baby_tracking else None,
```

Guard for empty credentials (raise a clear error or return `None`) so a missing
`.env` secret fails loudly rather than silently.

## 9. Builder / layout

In `builder.py`, `Section.BABY` currently appears only in `EVENING`. Add it to
**all four modes** (a newborn feeds around the clock), positioned where the
calendar currently sits:

```python
DashboardMode.MORNING:  (Section.TRAINS, Section.BABY, Section.CALENDAR, Section.WEATHER, ...),
DashboardMode.DAYTIME:  (Section.TRAINS, Section.BABY, Section.CALENDAR, Section.WEATHER, ...),
DashboardMode.EVENING:  (Section.CALENDAR_TOMORROW, Section.BABY, ...),
DashboardMode.OVERNIGHT:(Section.WEATHER, Section.BABY, Section.CALENDAR_TOMORROW),
```

`Section.BABY` is `EXPERIMENTAL` (gated by `baby_tracking` + data present), so it
still degrades gracefully when disabled.

## 10. Renderer

Add a `Section.BABY` handler to the `handlers` dict in `rendering/portrait.py`,
plus a `_draw_baby(painter, section)` method. Layout:

```
Last feed     3:40am
1h 20m ago
Formula · 80ml          (or:  Breast · right · 6m)
```

- Empty (`Feed` is `None` / `EMPTY`): show "No feeds logged yet".
- Unavailable: show "Feeds unavailable".
- Elapsed = `now - ended_at`, humanized ("5m ago", "1h 20m ago").

## 11. Config & env

`.env` (gitignored):

```
HUCKLEBERRY_EMAIL=pmcdowellthe3@gmail.com
HUCKLEBERRY_PASSWORD=<secret>
LAUNCHPAD_FEATURE_BABY_TRACKING=1
```

`.env.example`: document the two secrets (placeholder values) + the flag.

No systemd unit change required — `.env` is already loaded via `python-dotenv`
(the `tfl` extra) and the flag is read from settings.

## 12. Dependencies

`pyproject.toml` — add a `baby` extra (or fold into an existing extra):

```
baby = ["huckleberry-api==0.2.2"]
```

Reprovision on the Pi:

```bash
cd /opt/launchpad
source .venv/bin/activate
pip install -e ".[dev,render,tfl,web,baby]"
```

## 13. Decisions & conventions

- **Time since ended** — breast: `start + durations`; bottle: `start`.
- **Single child** — `childList[0]` for v1; multi-child is future work.
- **Lookback** — query the last 7 days (default) and take the max `start`.
- **Units** — normalize to ml.
- **Always-on** — feed section in every mode.

## 14. Open items / future

- Multi-child support (child selector + name).
- Show feed *count* or a short history, not just the last feed.
- Optional "next feed due" hint (newborn ≈ every 2–3 h).
- `get_child()` returned `name=None` in testing; if the name is wanted on-screen,
  locate the correct name field in the child document first.
- Huckleberry API is unofficial — monitor for breakage; keep the `unavailable`
  fallback path healthy.
