# Schwabdev Streaming

**Source:** https://tylerebowers.github.io/Schwabdev/pages/stream.html
**Source code (verbatim):** https://raw.githubusercontent.com/tylerebowers/Schwabdev/main/schwabdev/stream.py
**Extraction date:** 2026-05-13
**Library:** schwabdev (Python WebSocket wrapper around Schwab Streamer API)

Cross-reference: streaming services + field IDs (13 services, 263 fields) distilled at `reference/schwab-api/market-data-documentation.md`. This page documents the schwabdev **wrapper**, not the underlying services.

---

## Module overview

Two public classes, both extending an internal `StreamBase`:

- **`Stream`** — runs an asyncio event loop in a **separate daemon thread**; usable from synchronous code.
- **`StreamAsync`** — runs in the caller's current event loop (no thread).

Both share the same service methods (`level_one_equities`, etc.), `basic_request`, subscription tracking, and reconnection logic.

> "Since websockets are asynchronous `schwabdev.Stream` runs an async event loop in a separate thread, allowing you to use the streamer in synchronous code."

---

## Constructor

```python
streamer = schwabdev.Stream(client)
# OR
streamer = schwabdev.StreamAsync(client)
```

```python
class Stream(StreamBase):
    def __init__(self, client):
        super().__init__(client.tokens, client._get_streamer_info, client.logger)

class StreamAsync(StreamBase):
    def __init__(self, client):
        super().__init__(client.tokens, client._get_streamer_info, client.logger)
        self._task = None
```

`StreamBase.__init__` signature:

```python
class StreamBase:
    def __init__(self, tokens, get_streamer_info, logger: logging.Logger):
        """
        Initialize the stream object to stream data from Schwab Streamer

        Args:
            client (Client): Client object needed to get streamer info
        """
```

Internal state initialized:

| Attribute | Default | Purpose |
|---|---|---|
| `_tokens` | from client | tokens object (provides `access_token`) |
| `_get_streamer_info` | `client._get_streamer_info` | function called per connect to fetch streamer info |
| `_logger` | `client.logger` | logger |
| `_websocket` | `None` | active websocket |
| `_event_loop` | `None` | asyncio loop |
| `_thread` | `None` | runner thread (Stream only) |
| `_loop_ready` | `threading.Event()` | signals loop is ready |
| `_should_stop` | `True` | main loop control |
| `_backoff_time` | `2.0` | initial reconnect backoff (seconds) |
| `_streamer_info` | `None` | cached streamer info from API |
| `_request_id` | `0` | monotonic request id counter |
| `active` | `False` | public flag: is the stream live |
| `subscriptions` | `{}` | `{service: {key: [fields]}}` — replayed on reconnect |

---

## Streamer authentication / login handshake (VERBATIM)

The streamer URL + login parameters are fetched per connection via `_get_streamer_info()` (which the Schwab client populates from `GET /userPreference`).

The handshake is executed inside `_run_streamer`:

```python
async with websockets.connect(self._streamer_info.get('streamerSocketUrl'), ping_timeout=ping_timeout) as self._websocket:
    self._logger.debug("Connected to streaming server.")
    login_payload = self.basic_request(service="ADMIN",
                                       command="LOGIN",
                                       parameters={"Authorization": self._tokens.access_token,
                                                   "SchwabClientChannel": self._streamer_info.get("schwabClientChannel"),
                                                   "SchwabClientFunctionId": self._streamer_info.get("schwabClientFunctionId")})
    await self._websocket.send(json.dumps(login_payload))
    self._loop_ready.set()

    await call_receiver(await self._websocket.recv(), **kwargs)  # receive login response
    self.active = True
```

The LOGIN request is wrapped by `basic_request`, which adds these required envelope fields on every request:

```python
request = {"service": service.upper(),
           "command": command.upper(),
           "requestid": self._request_id,
           "SchwabClientCustomerId": self._streamer_info.get("schwabClientCustomerId"),
           "SchwabClientCorrelId": self._streamer_info.get("schwabClientCorrelId")}
if parameters is not None and len(parameters) > 0: request["parameters"] = parameters
```

So the on-the-wire LOGIN looks like:

```json
{
  "service": "ADMIN",
  "command": "LOGIN",
  "requestid": 1,
  "SchwabClientCustomerId": "<from streamer info>",
  "SchwabClientCorrelId": "<from streamer info>",
  "parameters": {
    "Authorization": "<access_token>",
    "SchwabClientChannel": "<from streamer info>",
    "SchwabClientFunctionId": "<from streamer info>"
  }
}
```

The LOGOUT request (sent in `stop()`) is the ADMIN/LOGOUT counterpart:

```python
self.send(self.basic_request(service="ADMIN", command="LOGOUT"), record=False)
```

### Token usage notes

- `_tokens.access_token` is read **at the moment of LOGIN** (once per connect/reconnect). If a reconnect happens, a fresh `access_token` value is re-read from the tokens object — so an external refresh (the schwabdev client's token refresher) will be picked up on the next reconnect.
- `_get_streamer_info()` is **also re-invoked** on every (re)connect attempt. If it raises but a previous `_streamer_info` is cached, the stream proceeds with the cached value:
  > "Error getting streamer info, but previous streamer info is available, trying to start stream with previous streamer info."

---

## Lifecycle

### `Stream.start(...)`

```python
def start(self, receiver=print, daemon: bool = True, ping_interval: int = 20, **kwargs):
    """
    Start the stream

    Args:
        receiver (function, optional): function to call when data is received. Defaults to print.
        daemon (bool, optional): whether to run the thread in the background (as a daemon). Defaults to True.
        ping_interval (int, optional): interval in seconds to send pings to the streamer. Defaults to 20.
    """
```

Spawns `threading.Thread(target=_start_asyncio, daemon=daemon)` which calls `asyncio.run(self._run_streamer(receiver, ping_interval, **kwargs))`. Waits up to 4.0 seconds for the loop to become ready (`self._loop_ready.wait(timeout=4.0)`). Re-entrancy is guarded — if already active and the thread is alive, a warning is logged and the call is a no-op.

NOTE: the `ping_interval` parameter is passed into `_run_streamer` as `ping_timeout=ping_interval` — internally the library uses the websockets `ping_timeout` setting, not `ping_interval` per se. Default 20s.

### `Stream.stop(clear_subscriptions: bool = True)`

```python
def stop(self, clear_subscriptions: bool = True):
    """
    Stop the stream

    Args:
        clear_subscriptions (bool, optional): clear records. Defaults to True.
    """
```

Behavior:
1. If `clear_subscriptions=True`, clears `self.subscriptions = {}`.
2. Sets `self._should_stop = True`.
3. If active + websocket present, sends `ADMIN/LOGOUT` (with `record=False` so the LOGOUT itself doesn't get recorded as a subscription).
4. Schedules `self._websocket.close()` via `asyncio.run_coroutine_threadsafe(...).result(timeout=5)`.
5. Joins the thread with `timeout=5`.

Also wired as context-manager exit + `__del__` finalizer.

### `Stream.start_auto(...)`

```python
def start_auto(self, receiver=print,
               start_time: datetime.time = datetime.time(9, 29, 0),
               stop_time: datetime.time = datetime.time(16, 0, 0),
               on_days: list[int] = [0,1,2,3,4],
               now_timezone: zoneinfo.ZoneInfo = zoneinfo.ZoneInfo("America/New_York"),
               daemon: bool = True, **kwargs):
    """
    Start the stream automatically at market open and close, will NOT erase subscriptions
    """
```

Spawns a daemon checker thread that polls every 30 seconds:
- If now is in `[start_time, stop_time]` AND `now.weekday() in on_days` AND not active → call `self.start(...)`.
- If outside hours AND active → call `self.stop(clear_subscriptions=False)` (subscriptions retained for next session).

Day-of-week mapping: `0 = Monday, ..., 6 = Sunday`. Default `[0,1,2,3,4]` = Mon–Fri.

If launched outside active hours, logs: `"Stream was started outside of active hours and will launch when in hours."`

### Context manager + finalizer

```python
def __enter__(self):
    self.start()
    return self

def __exit__(self, exc_type, exc_value, traceback):
    self.stop()

def __del__(self):
    self.stop()
```

### `StreamAsync` lifecycle differences

```python
async def start(self, receiver=print, ping_interval: int = 20, **kwargs):
    """
    Start the stream in the *current* event loop (no thread).
    """
```

```python
async def start_auto(self, receiver=print,
                     start_time: datetime.time = datetime.time(9, 29, 0),
                     stop_time: datetime.time = datetime.time(16, 0, 0),
                     on_days: list[int] | tuple[int] = (0,1,2,3,4),
                     now_timezone: zoneinfo.ZoneInfo = zoneinfo.ZoneInfo("America/New_York"),
                     daemon: bool = True, **kwargs):
```

```python
async def stop(self, clear_subscriptions: bool = True):
    """
    Stop the stream started with start_async.
    """
```

`__aenter__` / `__aexit__` provided for `async with` use. No background thread; `_task` is an `asyncio.Task` created via `self._event_loop.create_task(self._run_streamer(...))`.

---

## Reconnection / heartbeat / backoff

Driven entirely inside `_run_streamer`'s outer `while not self._should_stop:` loop. Behavior by exception type:

| Exception | Action |
|---|---|
| `ConnectionClosedOK` / `ConnectionClosed` with code `1000` | Log info, **break** (graceful close). |
| `ConnectionClosedOK` / `ConnectionClosed` during shutdown | Log info, **break**. |
| `ConnectionClosedOK` / `ConnectionClosed` abnormal | Log warning with elapsed time, wait backoff, **reconnect**. |
| `ConnectionClosedError` AND elapsed ≤ 90s | Treated as "likely no subscriptions, invalid login, or lost connection." **Do not restart.** Log warning + break. |
| `ConnectionClosedError` AND elapsed > 90s | Log error, wait backoff, **reconnect**. |
| Any other `Exception` | Log error + warning, wait backoff, **reconnect**. |

Backoff logic:

```python
async def _wait_for_backoff(self):
    await asyncio.sleep(self._backoff_time)
    self._backoff_time = min(self._backoff_time * 2, 120)
```

Starts at `2.0`s; doubles each failure; capped at `120`s. **Resets to `2.0`** after a successful login + subscription replay (right before entering the main listener loop).

On successful reconnect, the library **replays subscriptions automatically**:

```python
# send subscriptions (that are recorded (queued or previously sent))
for service, subs in self.subscriptions.items():
    grouped: dict[str, list[str]] = {} # group subscriptions by fields for more efficient requests
    for key, fields in subs.items():
        grouped.setdefault(self._list_to_string(fields), []).append(key)
    reqs = [] # list of requests to send for this service
    for fields, keys in grouped.items():
        reqs.append(self.basic_request(service=service, command="ADD", parameters={"keys": self._list_to_string(keys), "fields": fields}))
    if reqs:
        self._logger.debug(f"Sending subscriptions: {reqs}")
        await self._websocket.send(json.dumps({"requests": reqs}))
        await call_receiver(await self._websocket.recv(), **kwargs)
```

Heartbeats are handled by the `websockets` library's `ping_timeout` parameter (default 30s in `_run_streamer`, overridden to 20s by `Stream.start`).

> "The stream will close after ~30 seconds if there are no subscriptions."

---

## Subscriptions

### Subscription parameter format

Keys + fields can be passed as either:
- A **comma-separated string**: `"AMD,INTC"`, `"0,1,2,3"`
- A **list / tuple / set** of strings: `["AMD", "INTC"]`, `["0","1","2","3"]`

Internal conversion via `Stream._list_to_string`:

```python
@staticmethod
def _list_to_string(ls: list | str | tuple | set):
    """
    Convert a list to a string (e.g. [1, "B", 3] -> "1,B,3"), or passthrough if already a string
    """
    if isinstance(ls, str): return ls
    elif hasattr(ls, '__iter__'): return ",".join(map(str, ls))
    else: return str(ls)
```

### Commands

All subscribe helpers accept `command: str = "ADD"`. Valid commands per `basic_request`:

```
"SUBS"   - replace all subscriptions for the service with this set
"ADD"    - add to existing subscriptions (default for everything except ACCT_ACTIVITY)
"UNSUBS" - remove these keys
"VIEW"   - change fields for all currently-subscribed keys (no key change)
"LOGIN"  - admin (used internally)
"LOGOUT" - admin (used internally)
```

`ACCT_ACTIVITY` defaults to `"SUBS"` and only accepts `"SUBS"` / `"UNSUBS"`.

### Constraints

- **Maximum keys per subscription: 500.**
  > "The maximum number of keys that can be subscribed to at once is **500**."
- **Field `"0"` must always be included in the fields list.** (`"0"` is the key/symbol itself in all services.)

### `basic_request`

```python
def basic_request(self, service: str, command: str, parameters: dict | None = None):
    """
    Create a basic request (all requests follow this format)

    Args:
        service (str): service to use
        command (str): command to use ("SUBS"|"ADD"|"UNSUBS"|"VIEW"|"LOGIN"|"LOGOUT")
        parameters (dict, optional): parameters to use. Defaults to None.

    Returns:
        dict: request
    """
```

Builds the wire-format envelope (see LOGIN handshake section above). Strips `None`-valued parameters. Increments `_request_id`. Raises `ConnectionError("Streamer info unavailable")` if `_streamer_info` cannot be obtained.

### `send(...)` (Stream — sync wrapper)

```python
def send(self, requests: list | dict, record: bool=True):
    """
    Send a request to the stream

    Args:
        requests (list | dict): list of requests or a single request
    """
```

- Wraps single dicts to a list.
- Calls `_record_request` per request (unless `record=False`) — this updates `self.subscriptions` so reconnects can replay.
- If event loop not initialized OR not active → request is queued by virtue of being already recorded in `self.subscriptions`; logs `"Stream event loop not initialized yet; request queued."` or `"Stream is not active, request queued."`. (Queue is the subscription dict itself; replayed on next successful login.)
- Otherwise marshals via `asyncio.run_coroutine_threadsafe(self._websocket.send(json.dumps({"requests": requests})), self._event_loop)`.

### `send_async(...)` (Stream — async variant on the sync class)

```python
async def send_async(self, requests: list | dict):
    """
    Send a request to the stream
    """
```

Same behavior as `send`, but awaits the wrapped future for backpressure. Always records.

### `StreamAsync.send(...)`

```python
async def send(self, requests: list | dict, record: bool=True):
    """
    Send a request to the stream
    """
```

Native coroutine — directly awaits `self._websocket.send(...)`.

### Subscription helper methods (all share the same signature shape)

Each returns a request `dict` — pass through `streamer.send(...)` to actually send.

```python
def level_one_equities(self, keys: str | list, fields: str | list, command: str = "ADD") -> dict
def level_one_options(self, keys: str | list, fields: str | list, command: str = "ADD") -> dict
def level_one_futures(self, keys: str | list, fields: str | list, command: str = "ADD") -> dict
def level_one_futures_options(self, keys: str | list, fields: str | list, command: str = "ADD") -> dict
def level_one_forex(self, keys: str | list, fields: str | list, command: str = "ADD") -> dict
def nyse_book(self, keys: str | list, fields: str | list, command: str = "ADD") -> dict
def nasdaq_book(self, keys: str | list, fields: str | list, command: str = "ADD") -> dict
def options_book(self, keys: str | list, fields: str | list, command: str = "ADD") -> dict
def chart_equity(self, keys: str | list, fields: str | list, command: str = "ADD") -> dict
def chart_futures(self, keys: str | list, fields: str | list, command: str = "ADD") -> dict
def screener_equity(self, keys: str | list, fields: str | list, command: str = "ADD") -> dict
def screener_options(self, keys: str | list, fields: str | list, command: str = "ADD") -> dict
def account_activity(self, keys="Account Activity", fields="0,1,2,3", command: str = "SUBS") -> dict
```

Service identifier mapping:

| Helper | Schwab service name |
|---|---|
| `level_one_equities` | `LEVELONE_EQUITIES` |
| `level_one_options` | `LEVELONE_OPTIONS` |
| `level_one_futures` | `LEVELONE_FUTURES` |
| `level_one_futures_options` | `LEVELONE_FUTURES_OPTIONS` |
| `level_one_forex` | `LEVELONE_FOREX` |
| `nyse_book` | `NYSE_BOOK` |
| `nasdaq_book` | `NASDAQ_BOOK` |
| `options_book` | `OPTIONS_BOOK` |
| `chart_equity` | `CHART_EQUITY` |
| `chart_futures` | `CHART_FUTURES` |
| `screener_equity` | `SCREENER_EQUITY` |
| `screener_options` | `SCREENER_OPTION` (singular — note divergence) |
| `account_activity` | `ACCT_ACTIVITY` |

### Key formats (from docstrings, verbatim)

**`level_one_options` / `options_book`** — Contract format:
> `[Underlying Symbol (6 characters including spaces) | Expiration (6 characters) | Call/Put (1 character) | Strike Price (5+3=8 characters)]`
> Expiration is in `YYMMDD` format. Example: `"GOOG  240809C00095000"`, `"AAPL  240517P00190000"`, `"SPXW  251208C06880000"`.

**`level_one_futures` / `chart_futures`** — Key format:
> `'/' + 'root symbol' + 'month code' + 'year code'`
> month code is 1 character: (F: Jan, G: Feb, H: Mar, J: Apr, K: May, M: Jun, N: Jul, Q: Aug, U: Sep, V: Oct, X: Nov, Z: Dec)
> year code is 2 characters (i.e. 2024 = 24)
> Example: `"/ESF24"`, `"/GCG24"`, `"/ES"`

**`level_one_futures_options`** — Key format:
> `'.' + '/' + 'root symbol' + 'month code' + 'year code' + 'Call/Put code' + 'Strike Price'`
> month code is 1 character: (F: Jan, G: Feb, H: Mar, J: Apr, K: May, M: Jun, N: Jul, Q: Aug, U: Sep, V: Oct, X: Nov, Z: Dec)
> year code is 2 characters (i.e. 2024 = 24)
> Call/Put code is 1 character: (C: Call, P: Put)
> Example: `"./OZCZ23C565"`, `"./OGG26C4240"`

**`level_one_forex`** — Key format:
> `'from currency' + '/' + 'to currency'`
> Example: `"EUR/USD"`, `"JPY/USD"`

**`screener_equity`** — Key format:
> `(PREFIX)_(SORTFIELD)_(FREQUENCY)`
> Prefix: ($COMPX, $DJI, $SPX.X, INDEX_AL, NYSE, NASDAQ, OTCBB, EQUITY_ALL)
> Sortfield: (VOLUME, TRADES, PERCENT_CHANGE_UP, PERCENT_CHANGE_DOWN, AVERAGE_PERCENT_VOLUME)
> Frequency: (0 (all day), 1, 5, 10, 30, 60)
> Example: `"$DJI_PERCENT_CHANGE_UP_60"`, `"NASDAQ_VOLUME_30"`

**`screener_options`** — Key format:
> `(PREFIX)_(SORTFIELD)_(FREQUENCY)`
> Prefix: (OPTION_PUT, OPTION_CALL, OPTION_ALL)
> Sortfield: (VOLUME, TRADES, PERCENT_CHANGE_UP, PERCENT_CHANGE_DOWN, AVERAGE_PERCENT_VOLUME)
> Frequency: (0 (all day), 1, 5, 10, 30, 60)
> Example: `"OPTION_PUT_PERCENT_CHANGE_UP_60"`, `"OPTION_CALL_TRADES_30"`

### Subscription tracking (`_record_request`)

```python
def _record_request(self, request: dict):
    """
    Record the request into self.subscriptions (for the event of crashes)
    """
```

Per-command effect on `self.subscriptions[service]`:

- `ADD`: union new keys (union fields if key already present).
- `SUBS`: **replace** the entire `subscriptions[service]` dict with the new keys/fields.
- `UNSUBS`: delete listed keys from `subscriptions[service]`.
- `VIEW`: overwrite fields on **all** currently-subscribed keys for the service.

This dict is replayed on every successful reconnect (see Reconnection section).

---

## Callback / response handler pattern

The receiver is a user-supplied callable passed to `start(...)` (sync) or `start(...)` (async). Two flavors are detected automatically:

```python
is_async_receiver = True if asyncio.iscoroutinefunction(receiver_func) else False
async def call_receiver(response, **kwargs):
    if is_async_receiver:
        await receiver_func(response, **kwargs)
    else:
        receiver_func(response, **kwargs)
```

- **Sync receiver**: called inline in the async loop's thread. **Schwabdev docs warn:** handlers "should not be too taxing on the system as you don't want the response handler to fall behind the streamer."
- **Async receiver**: awaited inline.

The receiver is invoked for:
1. **The LOGIN response** (one call).
2. **Each subscription-batch ACK** during replay (one call per service group on reconnect).
3. **Every streamed message** thereafter in the main listener loop.

Messages are passed as **raw JSON strings** (the result of `await self._websocket.recv()`); the receiver must `json.loads` to inspect.

Any `**kwargs` passed to `start(...)` / `start_async(...)` are forwarded to every receiver invocation.

Recommended decoupling pattern (verbatim from docs):

```python
data = []
def my_handler(message):
    data.append("TEST" + message)

streamer.start(my_handler)

while True:
    if data:
        print(data.pop(0))
```

---

## Examples (verbatim from docs)

### Instantiation

```python
import schwabdev
client = schwabdev.Client(...)
# client = schwabdev.ClientAsync(...) # For an asynchronous client
streamer = schwabdev.Stream(client)
# streamer = schwabdev.StreamAsync(client) # For an asynchronous streamer
```

### Basic start with custom handler

```python
data = []
def my_handler(message):
    data.append("TEST" + message)

streamer.start(my_handler)

while True:
    if data:
        print(data.pop(0))
```

### Auto start/stop at market hours

```python
streamer.start_auto(
    receiver=print,
    start_time=datetime.time(9, 29, 0),
    stop_time=datetime.time(16, 0, 0),
    on_days=(0,1,2,3,4),
    now_timezone=zoneinfo.ZoneInfo("America/New_York"),
    daemon=True,
)
```

### Four equivalent ways to subscribe

```python
# Every way to subscribe to the fields 0,1,2,3 for equities "AMD" and "INTC"
streamer.send(streamer.level_one_equities("AMD,INTC", "0,1,2,3"))
streamer.send(streamer.level_one_equities(["AMD", "INTC"], ["0", "1", "2", "3"]))
streamer.send(streamer.level_one_equities("AMD,INTC", "0,1,2,3", command="ADD"))
streamer.send(
    streamer.basic_request(
        "LEVELONE_EQUITIES",
        "ADD",
        parameters={"keys": "AMD,INTC", "fields": "0,1,2,3"},
    )
)

# With await for asynchronous streamer:
await streamer.send(...)
```

### `send_async` from a sync streamer

```python
await streamer.send_async(streamer.level_one_equities("AMD,INTC", "0,1,2,3"))
```

### Sample response — LEVELONE_EQUITIES

```python
> streamer.send(streamer.level_one_equities("AMD,INTC", "0,1,2,3,4,5,6,7,8"))
{
  "data": [
    {
      "service": "LEVELONE_EQUITIES",
      "timestamp": 1765081984668,
      "command": "SUBS",
      "content": [
        {
          "1": 217.86, "2": 217.95, "3": 217.93,
          "4": 200, "5": 100, "6": "P", "7": "P", "8": 33292396,
          "key": "AMD", "delayed": false,
          "assetMainType": "EQUITY", "assetSubType": "COE", "cusip": "007903107"
        },
        {
          "1": 41.43, "2": 41.44, "3": 41.44,
          "4": 200, "5": 400, "6": "P", "7": "U", "8": 103042015,
          "key": "INTC", "delayed": false,
          "assetMainType": "EQUITY", "assetSubType": "COE", "cusip": "458140100"
        }
      ]
    }
  ]
}
```

### Sample response — LEVELONE_OPTIONS

```python
> streamer.send(streamer.level_one_options("SPXW  251208C06880000", "0,1,2,3,4,5,6,7,8"))
{
  "data": [{
    "service": "LEVELONE_OPTIONS",
    "timestamp": 1765082498588,
    "command": "SUBS",
    "content": [{
      "1": "SPXW 12/08/2025 6880.00 C",
      "2": 10.2, "3": 10.6, "4": 10.6, "5": 28.9, "6": 6.9, "7": 9.15, "8": 7961,
      "key": "SPXW  251208C06880000", "delayed": false, "assetMainType": "OPTION"
    }]
  }]
}
```

### Sample response — LEVELONE_FUTURES

```python
> streamer.send(streamer.level_one_futures("/ES", "0,1,2,3,4,5,6"))
{
  "data": [{
    "service": "LEVELONE_FUTURES",
    "timestamp": 1765083430060,
    "command": "SUBS",
    "content": [{
      "1": 6879.25, "2": 6879.75, "3": 6879.5,
      "4": 11, "5": 4, "6": "?",
      "key": "/ES", "delayed": false, "assetMainType": "FUTURE"
    }]
  }]
}
```

### Sample response — LEVELONE_FUTURES_OPTIONS

```python
> streamer.send(streamer.level_one_futures_options("./OGG26C4240", "0,1,2,3,4,5"))
{
  "data": [{
    "service": "LEVELONE_FUTURES_OPTIONS",
    "timestamp": 1765306046616,
    "command": "SUBS",
    "content": [{
      "1": 110.5, "2": 111.5, "3": 101.7, "4": 25, "5": 39,
      "key": "./OGG26C4240", "delayed": false, "assetMainType": "FUTURE_OPTION"
    }]
  }]
}
```

### Sample response — LEVELONE_FOREX

```python
> streamer.send(streamer.level_one_forex("EUR/USD", "0,1,2,3,4,5,6,7,8"))
{
  "data": [{
    "service": "LEVELONE_FOREX",
    "timestamp": 1765084326675,
    "command": "SUBS",
    "content": [{
      "1": 1.1643, "2": 1.16443, "3": 1.164365,
      "4": 100000, "5": 100000, "6": 0, "7": 0, "8": 1764971942013,
      "key": "EUR/USD", "delayed": false, "assetMainType": "FOREX"
    }]
  }]
}
```

### Sample response — CHART_EQUITY

```python
> streamer.send(streamer.chart_equity("AMD", "0,1,2,3,4,5,6,7,8"))
{
  "data": [{
    "service": "CHART_EQUITY",
    "timestamp": 1765307221991,
    "command": "SUBS",
    "content": [{
      "1": 425, "2": 221.133, "3": 221.18, "4": 221.02, "5": 221.02,
      "6": 11730, "7": 1765307100000, "8": 20431,
      "seq": 202, "key": "AMD"
    }]
  }]
}
```

Note: chart responses include a top-level `seq` field for sequence-tracked candle identification.

### Sample response — CHART_FUTURES

```python
> streamer.send(streamer.chart_futures("/ES", "0,1,2,3,4,5,6"))
{
  "data": [{
    "service": "CHART_FUTURES",
    "timestamp": 1765307265036,
    "command": "SUBS",
    "content": [{
      "1": 1765307160000, "2": 6858.25, "3": 6858.75,
      "4": 6857.75, "5": 6858.5, "6": 897,
      "seq": 2224, "key": "/ES"
    }]
  }]
}
```

### Sample response — SCREENER_EQUITY

```python
> streamer.send(streamer.screener_equity("NASDAQ_VOLUME_30", "0,1,2,3,4"))
{
  "data": [{
    "service": "SCREENER_EQUITY",
    "timestamp": 1765307304646,
    "command": "SUBS",
    "content": [{
      "1": 1765307297706, "2": "VOLUME", "3": 30,
      "4": [
        {"symbol": "WBD", "description": "WARNER BROS DISCOVER Series A",
         "lastPrice": 28.095, "netChange": 0.865, "netPercentChange": 0.03176643,
         "marketShare": 3.93926404, "totalVolume": 345149877, "volume": 13596365, "trades": 21302},
        {"symbol": "NVDA", "description": "NVIDIA CORP",
         "lastPrice": 184.59, "netChange": -0.96, "netPercentChange": -0.00517381,
         "marketShare": 1.52208891, "totalVolume": 345149877, "volume": 5253488, "trades": 67812}
        // ... more entries ...
      ],
      "key": "NASDAQ_VOLUME_30"
    }]
  }]
}
```

### Sample response — SCREENER_OPTION

```python
> streamer.send(streamer.screener_options("OPTION_CALL_TRADES_30", "0,1,2,3,4"))
{
  "data": [{
    "service": "SCREENER_OPTION",
    "timestamp": 1765307361611,
    "command": "SUBS",
    "content": [{
      "1": 1765307359566, "2": "TRADES", "3": 30,
      "4": [
        {"symbol": "SPXW  251209C06855000", "description": "SPXW   Dec 9 2025 6855.0 Call",
         "lastPrice": 2.75, "netChange": -8.891, "netPercentChange": -0.763766,
         "marketShare": 3.47850842, "totalVolume": 1761266, "volume": 21020, "trades": 7820}
        // ... more entries ...
      ],
      "key": "OPTION_CALL_TRADES_30"
    }]
  }]
}
```

### Account Activity subscription

```python
> streamer.send(streamer.account_activity("Account Activity", "0,1,2,3"))
```

(Defaults: `keys="Account Activity"`, `fields="0,1,2,3"`, `command="SUBS"`.)

### NYSE_BOOK / NASDAQ_BOOK / OPTIONS_BOOK responses

Book responses use a nested structure: `content[i]["2"]` is the bid stack, `content[i]["3"]` is the ask stack. Each price level contains: `"0"` = price, `"1"` = aggregate size, `"2"` = number of market participants, `"3"` = per-participant array with `"0"` = MPID, `"1"` = size, `"2"` = order id. Example (abbreviated — full sample available at source URL):

```python
> streamer.send(streamer.nyse_book(["F"], "0,1,2,3,4,5,6,7,8"))
{
  "data": [{
    "service": "NYSE_BOOK",
    "timestamp": 1765306323315,
    "command": "SUBS",
    "content": [{
      "1": 1765306322349,
      "2": [  // bids, top-of-book first
        {"0": 13.12, "1": 31600, "2": 9, "3": [
          {"0": "NYSE", "1": 8800, "2": 49786299},
          {"0": "IEXG", "1": 7900, "2": 49904606}
          // ... more participants ...
        ]}
        // ... more price levels ...
      ],
      "3": [  // asks
        {"0": 13.13, "1": 76300, "2": 14, "3": [ /* participants */ ]}
        // ... more price levels ...
      ],
      "key": "F"
    }]
  }]
}
```

---

## Threading model

**`Stream` (sync class):**
- `start()` spawns one daemon `threading.Thread` running `asyncio.run(_run_streamer(...))`.
- The asyncio event loop lives inside that thread; `self._event_loop` is set to it on entry.
- `send()` (called from the main/user thread) marshals via `asyncio.run_coroutine_threadsafe(...)`.
- `start_auto()` spawns a **second** daemon thread (the market-hours checker) that calls `start()` / `stop()` as hours come and go.
- Sync receivers execute **on the stream thread**, not the main thread — explicit synchronization (queues, locks) needed if the main thread reads handler state.

**`StreamAsync` (async class):**
- No thread. `start()` calls `self._event_loop = asyncio.get_running_loop()` then `create_task(...)` in the caller's loop.
- `_task` is an `asyncio.Task`; `stop()` awaits its completion.

---

## Helper / utility methods

### `_list_to_string` (static)

See "Subscription parameter format" above. Converts list/tuple/set → comma-joined string; passes strings through.

### `_record_request`

See "Subscription tracking" above. Maintains `self.subscriptions` for replay-on-reconnect.

### No built-in field-ID → field-name parser

The schwabdev `stream.py` source has **no helper to translate numeric field IDs into field names** (e.g., `"1"` → `"bidPrice"`). Responses are passed to the receiver as raw JSON strings; consumers are responsible for mapping field IDs themselves using the Schwab API field definitions (this project's mappings live at `reference/schwab-api/market-data-documentation.md`).

---

## Notes & constraints summary

| Constraint | Value | Source |
|---|---|---|
| Max keys per subscription | 500 | docs |
| Field "0" requirement | always include | docs |
| Idle disconnect | ~30s without subscriptions | docs |
| Default ping_interval | 20s (Stream.start) → passed as `ping_timeout` | source |
| Default ping_timeout | 30s (StreamBase._run_streamer) | source |
| Initial reconnect backoff | 2.0s | source |
| Backoff cap | 120s | source |
| Backoff growth | `min(prev * 2, 120)` | source |
| Backoff reset | after successful login + sub replay | source |
| "Quick crash" non-restart window | ≤90s elapsed → no reconnect | source |
| Subscription replay on reconnect | automatic via `self.subscriptions` | source |
| Token refresh | re-read `_tokens.access_token` on each reconnect | source |
| Streamer info refresh | `_get_streamer_info()` re-invoked per reconnect; falls back to cached value on transient error | source |
| Loop-ready timeout | `Stream.start` waits 4.0s for loop ready | source |
| Stop timeout | websocket close: 5s; thread join: 5s | source |
