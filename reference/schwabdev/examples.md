# Schwabdev Examples

**Source URL:** https://tylerebowers.github.io/Schwabdev/pages/examples.html
**Underlying examples:** https://github.com/tylerebowers/Schwabdev/tree/main/docs/examples
**Extraction date:** 2026-05-13
**Library:** schwabdev — unofficial Python wrapper for the Charles Schwab Trader API

---

## Overview

The Examples page is a directory of runnable scripts in the schwabdev repo at `docs/examples/`. The page itself contains minimal narrative; the substance is in the example files. All examples expect credentials in a project-local `.env` file consumed by `python-dotenv`.

### Required `.env` shape

```
app_key = "Your app key"
app_secret = "Your app secret"
callback_url = "https://127.0.0.1"
```

> **WARNING (from upstream docs):** "INCLUDE THIS FILE IN YOUR .gitignore TO AVOID LEAKING YOUR CREDENTIALS IF YOU ARE PUSHING TO GITHUB!"

### Top-level example files

| File | Purpose |
|------|---------|
| `api_demo.py` | Demonstrates every API call (order-placement section commented out for safety) |
| `async_api_calls.py` | Asynchronous API usage via `schwabdev.ClientAsync` |
| `jupyter_demo.ipynb` | Jupyter-notebook integration |
| `playground.py` | Interactive REPL session via `python -i playground.py` |
| `stream_demo.py` | Real-time streaming subscriptions |

### `extra/` subdirectory

`api_gui_demo.py`, `async_api_demo_parsed.py`, `async_playground.py`, `async_stream_demo.py`, `capture_callback.py`, `charting.py`, `concurrent_stream_calls.py`, `encrypted_db_setup.py`, `processing_streaming_data.py`, `template.py`, `translating_stream.py`.

---

## Minimal Client Instantiation (template.py)

The canonical minimal setup. **OAuth-relevant — preserve argument names exactly: `app_key`, `app_secret`, `callback_url`.**

```python
"""
Schwabdev Template Example
"""

import logging
import os
from dotenv import load_dotenv
import schwabdev


print("Welcome to Schwabdev, The Unofficial Schwab API Python Wrapper!")
print("Documentation: https://tylerebowers.github.io/Schwabdev/")

# place your app key and app secret in the .env file
load_dotenv()  # load environment variables from .env file

# warn user if they have not added their keys to the .env
if not len(os.getenv('app_key')) > 0 or not len(os.getenv('app_secret')) > 0:
    raise Exception("Add you app key and app secret to the .env file.")

# set logging level
logging.basicConfig(level=logging.INFO)

client = schwabdev.Client(os.getenv('app_key'), os.getenv('app_secret'), os.getenv('callback_url'))
#account_hash = client.linked_accounts().json()[0].get('hashValue')
streamer = schwabdev.Stream(client)
```

Notes:
- `schwabdev.Client(app_key, app_secret, callback_url)` is the standard 3-positional constructor.
- `schwabdev.Stream(client)` wraps a `Client` for streaming.
- The commented `account_hash = ...` line is the canonical idiom for picking the first linked account.

---

## Full API Demo (api_demo.py)

Demonstrates every REST call. Order-placement and order-modification calls are wrapped in a triple-quoted block so the demo is safe to run without firing live orders.

```python
"""
This file contains examples for every api call.
"""

import datetime
import logging
import os
from time import sleep
from dotenv import load_dotenv
import schwabdev

print("Welcome to Schwabdev, The Unofficial Schwab API Python Wrapper!")
print("Documentation: https://tylerebowers.github.io/Schwabdev/")

# place your app key and app secret in the .env file
load_dotenv()  # load environment variables from .env file

# set logging level
logging.basicConfig(level=logging.INFO)

# create client
client = schwabdev.Client(os.getenv('app_key'), os.getenv('app_secret'), os.getenv('callback_url'))

print("\nGet account number and hashes for linked accounts")
linked_accounts = client.linked_accounts().json()
print(linked_accounts)
account_hash = linked_accounts[0].get('hashValue') # this will get the first linked account
sleep(3)

print("\nGet details for all linked accounts")
print(client.account_details_all().json())
sleep(3)

print("\nGet specific account positions (uses default account, can be changed)")
print(client.account_details(account_hash, fields="positions").json())
sleep(3)

print("\nGet orders for a linked account")
print(client.account_orders(account_hash, datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30), datetime.datetime.now(datetime.timezone.utc)).json())
sleep(3)


order = {"orderType": "LIMIT",
            "session": "NORMAL",
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "price": '10.00',
            "orderLegCollection": [
                {"instruction": "BUY",
                "quantity": 1,
                "instrument": {"symbol": "INTC",
                                "assetType": "EQUITY"
                                }
                }
            ]
        }

# Uncomment below to enable order placing/details/cancelling demo
"""
resp = client.place_order(account_hash, order)
print(f"\nPlace an order status: {resp}")
order_id = resp.headers.get('location', '/').split('/')[-1] # get the order ID - if order is immediately filled then the id might not be returned
print(f"Order id: {order_id}")
sleep(3)

print("\nGet specific order details")
print(client.order_details(account_hash, order_id).json())
sleep(3)

print("\nCancel a specific order")
print(client.cancel_order(account_hash, order_id).json())
sleep(3)
"""

print("\nReplace specific order")
#client.replace_order(account_hash, order_id, order)
print("No demo implemented")
sleep(3)


print("\nGet up to 3000 orders for all accounts for the past 30 days")
print(client.account_orders_all(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30),
                                datetime.datetime.now(datetime.timezone.utc)).json())
sleep(3)


print("\nPreview an order")
print(client.preview_order(account_hash, order).json())


print("\nGet all transactions for an account")
print(client.transactions(account_hash, datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30), datetime.datetime.now(datetime.timezone.utc), "TRADE").json())
sleep(3)


print("\nGet details for a specific transaction")
#print(client.transaction_details(account_hash, transactionId).json())
print("No demo implemented")
sleep(3)


print("\nGet user preferences for an account")
print(client.preferences().json())
sleep(3)


print("\nGet a list of quotes")
print(client.quotes(["AAPL", "AMD"]).json())
sleep(3)

print("\nGet a single quote")
print(client.quote("INTC").json())
#print(client.quote("SPXW  241111P06000000").json()) # expired contract now, just an example
sleep(3)

print("\nGet an option chain")
print("Demo disabled to prevent flooding terminal.")
# print(client.option_chains("AAPL", contractType="CALL", range="OTM").json())
# Here is another example for SPX, note that if you call with just $SPX
# you will exceed the buffer on Schwab's end
# hence, the additional parameters to limit the size of return.
# print(client.option_chains("$SPX", contractType="CALL", range="ITM").json())
sleep(3)

print("\nGet an option expiration chain")
print(client.option_expiration_chain("AAPL").json())
sleep(3)

print("\nGet price history for a symbol")
print(client.price_history("AAPL", "year").json())
sleep(3)

print("\nGet movers for an index")
print(client.movers("$DJI").json())
sleep(3)

print("\nGet marketHours for a symbol")
print(client.market_hours(["equity", "option"]).json())
# print(client.market_hours("equity,option").json()) # also works
sleep(3)

print("\nGet marketHours for a market")
print(client.market_hour("equity").json())
sleep(3)

print("\nGet instruments for a symbol")
print(client.instruments("AAPL", "fundamental").json())
sleep(3)

print("\nGet instruments for a cusip")
print(client.instrument_cusip("037833100").json())  # 037833100 = AAPL
sleep(3)
```

Key idioms surfaced:
- `client.linked_accounts().json()[0].get('hashValue')` — the canonical way to get the working account hash.
- Datetimes for date-range params are passed as timezone-aware `datetime` objects (UTC).
- `client.place_order(...)` returns a response whose `Location` header carries the new order ID: `resp.headers.get('location', '/').split('/')[-1]`. If the order is immediately filled, the ID may not be returned.
- Order payload schema example (LIMIT BUY 1 INTC @ $10.00) is shown verbatim.
- The big `$SPX` option-chain caveat: calling with just `$SPX` exceeds Schwab's buffer; use additional params (e.g., `contractType`, `range`) to limit return size.

---

## Streaming Subscriptions (stream_demo.py)

```python
"""
This file contains examples for stream requests.
"""

import logging
import os
import time
from dotenv import load_dotenv

import schwabdev


def main():
    # place your app key and app secret in the .env file
    load_dotenv()  # load environment variables from .env file

    # set logging level
    logging.basicConfig(level=logging.INFO)

    client = schwabdev.Client(os.getenv('app_key'), os.getenv('app_secret'), os.getenv('callback_url'))

    # define a variable for the steamer:
    streamer = schwabdev.Stream(client)


    # example of using your own response handler, prints to main terminal.
    # the first parameter is used by the stream, additional parameters are passed to the handler
    def my_handler(message):
        print("demo_handler: " + message)
    streamer.start(my_handler)

    # start steamer with default response handler (print):
    # streamer.start()

    # You can stream up to 500 keys.
    # By default all shortcut requests (below) will be "ADD" commands meaning the list of symbols will be added/appended
    # to current subscriptions for a particular service, however if you want to overwrite subscription (in a particular
    # service) you can use the "SUBS" command. Unsubscribing uses the "UNSUBS" command. To change the list of fields use
    # the "VIEW" command.


    # these three do the same thing
    # streamer.send(streamer.basic_request("LEVELONE_EQUITIES", "ADD", parameters={"keys": "AMD,INTC", "fields": "0,1,2,3,4,5,6,7,8"}))
    # streamer.send(streamer.level_one_equities("AMD,INTC", "0,1,2,3,4,5,6,7,8", command="ADD"))
    streamer.send(streamer.level_one_equities("AMD,INTC", "0,1,2,3,4,5,6,7,8"))


    # streamer.send(streamer.level_one_options("GOOGL 240712C00200000", "0,1,2,3,4,5,6,7,8")) # option contract examples will likely be outdated
    # streamer.send(streamer.level_one_options("SPY   241014C00580000", "0,1,2,3,4,5,6,7,8")) # option contract examples will likely be outdated
    # streamer.send(streamer.level_one_options("SPXW  251208C06880000", "0,1,2,3,4,5,6,7,8")) # option contract examples will likely be outdated

    # streamer.send(streamer.level_one_futures("/ES", "0,1,2,3,4,5,6"))

    # streamer.send(streamer.level_one_futures_options("./OZCZ23C565", "0,1,2,3,4,5")) # option contract examples will likely be outdated
    # streamer.send(streamer.level_one_futures_options("./OGG26C4140", "0,1,2,3,4,5")) # option contract examples will likely be outdated
    # streamer.send(streamer.level_one_futures_options("./OGG26C4240", "0,1,2,3,4,5")) # option contract examples will likely be outdated

    # streamer.send(streamer.level_one_forex("EUR/USD", "0,1,2,3,4,5,6,7,8"))

    # streamer.send(streamer.nyse_book(["F", "NIO"], "0,1,2,3"))

    # streamer.send(streamer.nasdaq_book("AMD", "0,1,2,3"))

    # streamer.send(streamer.options_book("GOOGL 251212C00315000", "0,1,2,3")) # option contract examples will likely be outdated

    # streamer.send(streamer.chart_equity("AMD", "0,1,2,3,4,5,6,7,8"))

    # streamer.send(streamer.chart_futures("/ES", "0,1,2,3,4,5,6"))

    # streamer.send(streamer.screener_equity("NASDAQ_VOLUME_30", "0,1,2,3,4"))

    # streamer.send(streamer.screener_options("OPTION_CALL_TRADES_30", "0,1,2,3,4"))

    # streamer.send(streamer.account_activity("Account Activity", "0,1,2,3"))


    # stop the stream after 30 seconds (since this is a demo)
    time.sleep(30)
    streamer.stop()
    # if you don't want to clear the subscriptions, set clear_subscriptions=False
    # streamer.stop(clear_subscriptions=False)
    # if True, the next time you start the stream it will resubscribe to the previous subscriptions
    # (except if program is restarted)


if __name__ == '__main__':
    print("Welcome to Schwabdev, The Unofficial Schwab API Python Wrapper!")
    print("Documentation: https://tylerebowers.github.io/Schwabdev/")
    main()  # call the user code above
```

Key streaming concepts:
- **Subscription cap:** up to 500 keys.
- **Commands:** `ADD` (default — append to subscription set), `SUBS` (overwrite), `UNSUBS` (remove), `VIEW` (change field set).
- **Three equivalent forms** for an equity subscription:
  - `streamer.basic_request("LEVELONE_EQUITIES", "ADD", parameters={"keys": ..., "fields": ...})`
  - `streamer.level_one_equities(symbols, fields, command="ADD")`
  - `streamer.level_one_equities(symbols, fields)` (default command="ADD")
- **Service shortcut methods:** `level_one_equities`, `level_one_options`, `level_one_futures`, `level_one_futures_options`, `level_one_forex`, `nyse_book`, `nasdaq_book`, `options_book`, `chart_equity`, `chart_futures`, `screener_equity`, `screener_options`, `account_activity`.
- **`streamer.stop(clear_subscriptions=False)`** preserves subscription state for resubscribe on next `start()` (within the same process).

---

## Async API Calls (async_api_calls.py)

```python
"""
Example of making concurrent asynchronous API calls to get quotes for multiple tickers.
"""
import os
import asyncio
import dotenv
import schwabdev

dotenv.load_dotenv()

# get concurrent quotes for multiple tickers

async def main():
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "AMD", "NVDA", "META", "INTC", "CSCO"]

    async with schwabdev.ClientAsync(os.getenv("app_key"), os.getenv("app_secret"), os.getenv("callback_url")) as client:

        print((await (await client.linked_accounts()).json()))

        async with asyncio.TaskGroup() as tg:
            results = [tg.create_task((await client.quotes(t)).json()) for t in tickers]

        print([result.result() for result in results])



if __name__ == "__main__":
    asyncio.run(main())
```

Notes:
- Async client is `schwabdev.ClientAsync` — same constructor signature as `Client`.
- Used as an async context manager: `async with ClientAsync(...) as client:`.
- Both the call AND the `.json()` are awaited: `(await (await client.linked_accounts()).json())`.
- Fan-out via `asyncio.TaskGroup`.

---

## Concurrent Streaming (extra/concurrent_stream_calls.py)

```python
"""
Example of making concurrent stream requests.
"""
import os
import asyncio
import dotenv
import logging
import schwabdev

dotenv.load_dotenv()

STOP_AT = 10 # number of messages to receive before stopping

logging.basicConfig(level=logging.INFO)

tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "AMD", "NVDA", "META", "INTC", "CSCO"]

async def main():

    data = []
    def response_handler(message):
        data.append(message)

    async with schwabdev.ClientAsync(os.getenv("app_key"), os.getenv("app_secret"), os.getenv("callback_url")) as client:
        streamer = schwabdev.StreamAsync(client)
        await streamer.start(response_handler)
        async with asyncio.TaskGroup() as tg:
            for t in tickers:
                tg.create_task(streamer.send(streamer.level_one_equities(t, fields="0,1,2,3,4,5,6,7,8,9")))

        counter = 0
        while True:
            if data:
                counter += 1
                print(data.pop(0))
            if counter == STOP_AT:
                await streamer.stop()
                break
            await asyncio.sleep(0.1)

if __name__ == "__main__":
    asyncio.run(main())
```

- Async streamer is `schwabdev.StreamAsync(client)`.
- Pattern: collect messages in a shared list inside the response handler; consume from the main coroutine.

---

## Processing Stream Data (extra/processing_streaming_data.py)

Demonstrates the recommended pattern: response handler ONLY appends to a shared list; processing happens in the main loop, so a slow consumer cannot block stream message reception.

```python
"""
This file is an example of how to process streaming data.
While you can process completely in the response handler this could leave the stream with a backlog.
The preferred method is to use a shared list, shown here as "shared_list"
"""
import json
import logging
import os
import time
from datetime import datetime

import dotenv

import schwabdev

# load environment
dotenv.load_dotenv()

# warn user if they have not added their keys to the .env
if len(os.getenv('app_key')) != 32 or len(os.getenv('app_secret')) != 16:
    raise Exception("Add you app key and app secret to the .env file.")

# set logging level
logging.basicConfig(level=logging.INFO)

# make a client
client = schwabdev.Client(os.getenv('app_key'), os.getenv('app_secret'), os.getenv('callback_url'))
streamer = schwabdev.Stream(client)

# define a response handler
shared_list: list[str] = []


def response_handler(message):
    shared_list.append(message)

# start the stream and send in what symbols we want.
streamer.start(response_handler)
streamer.send(streamer.level_one_equities("AMD,INTC", "0,1,2,3,4,5,6,7,8"))


while True: # proccessing on list is done here
    # print the most recent message
    while len(shared_list) > 0: # while there is still data to consume from the list
        oldest_response = json.loads(shared_list.pop(0))  # get the oldest data from the list
        # print(oldest_response)
        for rtype, services in oldest_response.items():
            if rtype == "data":
                for service in services:
                    service_type = service.get("service", None)
                    service_timestamp = service.get("timestamp", 0)
                    contents = service.get("content", [])
                    for content in contents:
                        symbol = content.pop("key", "NO KEY")
                        fields = content
                        print(f"[{service_type} - {symbol}]({datetime.fromtimestamp(service_timestamp//1000)}): {fields}")
            elif rtype == "response":
                pass # this is a "login success" or "subscription success" or etc
            elif rtype == "notify":
                pass # this is a heartbeat (usually) which means that the stream is still alive
            else:
                # unidentified response type
                print(oldest_response)
    time.sleep(0.5) # slow down difference checking
```

Useful observations on raw stream message shape:
- Top-level keys: `data` (subscription tick data), `response` (login/subscription acks), `notify` (heartbeats).
- Each `data` entry has `service`, `timestamp` (ms epoch), `content` (list of per-symbol dicts).
- Per-symbol dict carries `key` (symbol) plus numeric-string field IDs.

---

## Translating Stream Field Numbers (extra/translating_stream.py)

`schwabdev.stream_fields` is a built-in mapping from service name → field-number → field-name. Use it to translate raw numeric field IDs into human names.

```python
"""
Example of translating field numbers to field names in a streaming response.
"""

import logging
import os
from dotenv import load_dotenv
import schwabdev
import json
import datetime



def translate_data(response) -> list[str]:
    """
    Translate field numbers to field names

    Returns:
        list[str]: list of field names
    """
    for item in response.get("data", []):
        if isinstance(item, dict):
            service = item.get("service", None)
            timestamp = item.get("timestamp", None)
            content = item.get("content", None)
            if timestamp:
                item["timestamp"] = datetime.datetime.fromtimestamp(timestamp / 1000)

            if service and content and service.startswith("LEVELONE_"):
                if isinstance(content, list):
                    for quote in content:
                        for field, value in quote.copy().items():
                            if field.isdigit():
                                new_field = translate_field(service, field)
                                quote[new_field] = quote.pop(field)

    return response


def translate_field(service: str, field: str|int) -> str:
    """
    Translate field number to field name

    Args:
        field (str|int): field number
    Returns:
        str: field name
    """
    mapping = schwabdev.stream_fields.get(service.upper(), None)
    if mapping is None:
        return str(field)
    try:
        if isinstance(mapping, dict):
            return mapping.get(field, str(field))
        elif isinstance(mapping, list):
            index = int(field)
            if 0 <= index < len(mapping):
                return mapping[index]
            else:
                return str(field)
        else:
            return str(field)
    except Exception:
        return str(field)

if __name__ == "__main__":
    print("Welcome to Schwabdev, The Unofficial Schwab API Python Wrapper!")
    print("Documentation: https://tylerebowers.github.io/Schwabdev/")

    # place your app key and app secret in the .env file
    load_dotenv()  # load environment variables from .env file

    # warn user if they have not added their keys to the .env
    if not len(os.getenv('app_key')) > 0 or not len(os.getenv('app_secret')) > 0:
        raise Exception("Add you app key and app secret to the .env file.")

    # set logging level
    logging.basicConfig(level=logging.INFO)

    client = schwabdev.Client(os.getenv('app_key'), os.getenv('app_secret'), os.getenv('callback_url'))
    streamer = schwabdev.Stream(client)

    def response_handler(msg):
        translated = translate_data(json.loads(msg))
        print(translated)


    streamer.start(response_handler)

    streamer.send(streamer.level_one_equities("AMD,INTC", "0,1,2,3,4,5,6,7,8"))
    # streamer.send(streamer.nyse_book(["F"], "0,1,2,3,4,5,6,7,8"))

    import time
    time.sleep(30)
    streamer.stop()
```

---

## OAuth Callback Capture (extra/capture_callback.py)

**OAuth-critical example.** Replaces copy/paste of the redirect URL with an injected local HTTPS server that captures the `code=` query param. Uses the **`call_on_auth=` Client kwarg** to inject a custom auth flow. Callback URL must include a free port (e.g. `https://127.0.0.1:7777`). Browser will warn about a self-signed cert — accept the warning; it's local-only.

```python
"""
This is an example of an injected callback capture server for Schwabdev's authentication process (no copy/pasting URLs during auth).
You must have a free port in your callback URL such as `https://127.0.0.1:7777`.
The browser will say that the connection is not secure (e.g. net::ERR_CERT_AUTHORITY_INVALID) because it is using a self-signed certificate, though this is fine because it is a local connection.
"""

import os
import ssl
import http.server
import datetime
import schwabdev
import dotenv
import logging
import webbrowser

def _generate_certificate(common_name="common_name", key_filepath="localhost.key", cert_filepath="localhost.crt"):
        """
        Generate a self-signed certificate for use in capturing the callback during authentication

        Args:
            common_name (str, optional): Common name for the certificate. Defaults to "common_name".
            key_filepath (str, optional): Filepath for the key file. Defaults to "localhost.key".
            cert_filepath (str, optional): Filepath for the certificate file. Defaults to "localhost.crt".

        Notes:
            Schwabdev will change the filepaths to ~/.schwabdev/* (user's home directory)

        """
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID

        # make folders for cert files
        os.makedirs(os.path.dirname(key_filepath), exist_ok=True)
        os.makedirs(os.path.dirname(cert_filepath), exist_ok=True)

        # create a key pair
        key = rsa.generate_private_key(public_exponent=65537,key_size=2048)

        # create a self-signed cert
        builder = x509.CertificateBuilder()
        builder = builder.subject_name(x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Schwabdev"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Authentication"),
        ]))
        builder = builder.issuer_name(x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]))
        builder = builder.not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        builder = builder.not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3650))
        builder = builder.serial_number(x509.random_serial_number())
        builder = builder.public_key(key.public_key())
        builder = builder.add_extension(
            x509.SubjectAlternativeName([x509.DNSName(common_name)]),
            critical=False,
        )
        builder = builder.sign(key, hashes.SHA256())
        with open(key_filepath, "wb") as f:
            f.write(key.private_bytes(encoding=serialization.Encoding.PEM,
                                      format=serialization.PrivateFormat.TraditionalOpenSSL,
                                      encryption_algorithm=serialization.NoEncryption()))
        with open(cert_filepath, "wb") as f:
            f.write(builder.public_bytes(serialization.Encoding.PEM))
        print(f"Certificate generated and saved to {key_filepath} and {cert_filepath}")

def _launch_capture_server(url_base, url_port):

    # class used to share code outside the http server
    class SharedCode:
        def __init__(self):
            self.code = ""

    # custom HTTP handler to silence logger and get code
    class HTTPHandler(http.server.BaseHTTPRequestHandler):
        shared = None

        def log_message(self, format, *args):
            pass  # silence logger

        def do_GET(self):
            if self.path.find("code=") != -1:
                self.shared.code = f"{self.path[self.path.index('code=') + 5:self.path.index('%40')]}@"
            self.send_response(200, "OK")
            self.end_headers()
            self.wfile.write(b"You may now close this page.")

    shared = SharedCode()

    HTTPHandler.shared = shared
    httpd = http.server.HTTPServer((url_base, url_port), HTTPHandler)
    # httpd.socket.settimeout(1)

    cert_filepath = os.path.expanduser("~/.schwabdev/localhost.crt")
    key_filepath = os.path.expanduser("~/.schwabdev/localhost.key")
    if not (os.path.isfile(cert_filepath) and os.path.isfile(key_filepath)):  # this does not check validity
        _generate_certificate(common_name=url_base, cert_filepath=cert_filepath, key_filepath=key_filepath)

    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ctx.load_cert_chain(certfile=cert_filepath, keyfile=key_filepath)
    # ctx.load_default_certs()

    print(f"[Schwabdev] Listening on port {url_port} for callback...")
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    while len(shared.code) < 1:  # wait for code
        httpd.handle_request()

    httpd.server_close()
    return shared.code

def _custom_auth(auth_url):
    url_split = auth_url.split("://")[-1].split(":")
    url_base = url_split[0]
    url_port = url_split[-1]  # this may or may not have the port

    print(f"Opening browser for authentication at: {auth_url}")
    webbrowser.open(auth_url)  # open the callback url in the browser

    if  not url_port.isdigit():  # if there is a port then capture the callback url
        print("Could not find port in callback url, so you will have to copy/paste the url.")
    else:
        return _launch_capture_server(url_base, int(url_port))


if __name__ == "__main__":
    dotenv.load_dotenv()  # load environment variables from .env file

    logging.basicConfig(level=logging.INFO)

    client = schwabdev.Client(
        os.getenv('app_key'),
        os.getenv('app_secret'),
        os.getenv('callback_url'),
        call_on_auth=_custom_auth
    )

    # manually trigger the auth flow to demonstrate the callback capture
    client.tokens.update_tokens(force_refresh_token=True)

    print("Modified auth flow complete.")

    print(client.linked_accounts().json())
```

OAuth-relevant APIs exposed by this example:
- **`schwabdev.Client(..., call_on_auth=<callable>)`** — Client constructor accepts a `call_on_auth` callable. Schwabdev invokes it with the OAuth `auth_url` instead of running its default copy/paste flow. The callable returns the captured `code=...@` string.
- **`client.tokens.update_tokens(force_refresh_token=True)`** — manually trigger the auth flow (forces a refresh-token rotation, which is the OAuth flow that requires browser interaction).
- Schwabdev's default cert filepaths are `~/.schwabdev/localhost.crt` and `~/.schwabdev/localhost.key`.
- The callback URL parser splits on `:` and treats the last segment as the port if numeric — `https://127.0.0.1:7777` parses to base `127.0.0.1` + port `7777`.
- Captured `code` substring is `path[idx('code=')+5 : idx('%40')] + '@'` (`%40` is URL-encoded `@`).

---

## Encrypted Token Storage (extra/encrypted_db_setup.py)

**OAuth-critical example.** Shows the **`encryption=` Client kwarg** for encrypting the on-disk token store with Fernet symmetric encryption. The same key must be passed every subsequent Client construction to decrypt.

```python
"""
This example demonstrates how to set up an encrypted database for storing tokens using Schwabdev.
"""

import logging
import os
from dotenv import load_dotenv
import schwabdev
from cryptography.fernet import Fernet
import time

# place your app key and app secret in the .env file
load_dotenv()  # load environment variables from .env file

# warn user if they have not added their keys to the .env
if not len(os.getenv('app_key')) > 0 or not len(os.getenv('app_secret')) > 0:
    raise Exception("Add you app key and app secret to the .env file.")

# set logging level
logging.basicConfig(level=logging.INFO)

print("This script helps setup an encrypted tokens database for Schwabdev.")
time.sleep(3)
print("First, we need to generate an encryption key.")
time.sleep(3)
print("!!!! Save this key, you will need it each time you make a Client !!!!")
key = Fernet.generate_key()
print("Encryption key:", key.decode())
time.sleep(5)
input("Next, we will redo the authentication process to save the encrypted tokens. Press Enter to continue, or Ctrl+C to exit.")
os.environ['encryption'] = key.decode() # store the key in an environment variable
client = schwabdev.Client(os.getenv('app_key'), os.getenv('app_secret'), os.getenv('callback_url'), encryption=os.getenv('encryption'))
print("Now that you are authenticated, the encrypted tokens are saved in the database.")
print("You can now create new Client instances using the same encryption key to access the tokens.")
print("If you want to remove encryption, create a new Client without the encryption parameter and redo the authentication process.")
```

OAuth-relevant Client kwarg:
- **`encryption=<fernet_key_string>`** — pass a Fernet key (UTF-8 decoded) to encrypt the token store. To decrypt later, instantiate with the same `encryption=` value. To disable, omit the kwarg and redo auth.

---

## Interactive Playground (playground.py)

Run with `python -i playground.py` to drop into a Python REPL with `client` and `streamer` already bound.

```python
!!! Run this file with `python -i playground.py` !!!
It allows you to enter python code to test the api without restarting the whole program.


import logging
import sys
import os
from dotenv import load_dotenv
import schwabdev

if not sys.flags.interactive:
    print("This file is intended to be run in interactive mode, with \"python -i playground.py\"\n"*3)
    sys.exit(1)

print("Welcome to Schwabdev, The Unofficial Schwab API Python Wrapper!")
print("Documentation: https://tylerebowers.github.io/Schwabdev/")

# place your app key and app secret in the .env file
load_dotenv()  # load environment variables from .env file

# warn user if they have not added their keys to the .env
if not len(os.getenv('app_key')) > 0 or not len(os.getenv('app_secret')) > 0:
    raise Exception("Add you app key and app secret to the .env file.")

# set logging level
logging.basicConfig(level=logging.INFO)

client = schwabdev.Client(os.getenv('app_key'), os.getenv('app_secret'), os.getenv('callback_url'))
#account_hash = client.linked_accounts().json()[0].get('hashValue')
streamer = schwabdev.Stream(client)
print("Client and Streamer created as 'client' and 'streamer' variables, use quit() to exit.")
```

---

## Client Constructor Reference (consolidated from examples)

Aggregated kwargs surfaced across the example set. Argument names preserved verbatim.

```python
schwabdev.Client(
    app_key,                # str — positional 1 — Schwab developer app key
    app_secret,             # str — positional 2 — Schwab developer app secret
    callback_url,           # str — positional 3 — registered OAuth redirect (e.g. "https://127.0.0.1" or "https://127.0.0.1:7777")
    call_on_auth=...,       # callable — custom OAuth flow handler (see capture_callback.py)
    encryption=...,         # str — Fernet key for encrypting on-disk token store (see encrypted_db_setup.py)
)
```

Async variant:

```python
schwabdev.ClientAsync(app_key, app_secret, callback_url)   # same signature; used as async context manager
```

Streamer variants:

```python
schwabdev.Stream(client)          # sync streamer
schwabdev.StreamAsync(client)     # async streamer
```

**Note:** The `tokens_file` argument requested in the operator's brief is NOT exposed in the published examples. Token-store customization in schwabdev is done via the `encryption=` kwarg (which encrypts the default store) or by manipulating `client.tokens` directly (e.g. `client.tokens.update_tokens(force_refresh_token=True)`). The default token file lives under `~/.schwabdev/`. If a `tokens_file` parameter exists in the underlying library, it is not demonstrated on the Examples page and would need to be discovered from `client.py` source or other doc pages.

---

## Cross-references

- Source repo examples directory: https://github.com/tylerebowers/Schwabdev/tree/main/docs/examples
- Project docs landing: https://tylerebowers.github.io/Schwabdev/
- Schwab developer portal (assumed): https://developer.schwab.com/

---

## Output samples

The Examples page does not include captured printed output. The example scripts call `.json()` on every response — the shape of each response is whatever Schwab's REST API returns for that endpoint. See `api_demo.py` for the canonical list of endpoints and parameter patterns; for response schemas refer to Schwab's API documentation (not part of the schwabdev examples page).
