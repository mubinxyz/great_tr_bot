# handlers/chart.py
import asyncio
import functools
import logging
from telegram.ext import CommandHandler
from telegram import Update
from services.chart_service import get_chart
from utils.normalize_data import normalize_timeframe, to_unix_timestamp

logger = logging.getLogger(__name__)
INTER_CHART_DELAY = 0.15
DEFAULT_OUTPUTSIZE = 200
DEFAULT_TIMEFRAME = "15"
DATE_FORCED_OUTPUTSIZE = 9999


def _merge_quoted_tokens(tokens: list[str]) -> list[str]:
    """
    Reconstruct tokens that were split inside quotes.
    Example: ['"2024-08-01', '14:30:00"'] -> ['"2024-08-01 14:30:00"']
    Supports single or double quotes.
    """
    merged = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if (t.startswith('"') and not t.endswith('"')) or (t.startswith("'") and not t.endswith("'")):
            quote = t[0]
            buf = [t]
            i += 1
            while i < len(tokens) and not tokens[i].endswith(quote):
                buf.append(tokens[i])
                i += 1
            if i < len(tokens):
                # append the closing token
                buf.append(tokens[i])
                i += 1
            # join with space (restore original) and append
            merged.append(" ".join(buf))
        else:
            merged.append(t)
            i += 1
    return merged


async def chart_command(update: Update, context):
    """
    /chart <symbols [required]> [timeframes default=15m] [outputsize default=200] [from_date] [to_date]

    Rules:
      - If two quoted dates provided, date-range mode -> outputsize = DATE_FORCED_OUTPUTSIZE.
      - Otherwise a positive integer in the third position sets outputsize.
      - Timeframe tokens like 1,5,15,60,1h,4h,D,W,M are accepted.
      - Dates must be quoted if they contain spaces (e.g. "2024-08-01 14:30:00").
    """
    try:
        if len(context.args) < 1:
            await update.message.reply_text(
                "Usage: /chart <symbols> [timeframe=15] [outputsize=200] [from_date] [to_date]\n"
                "Examples:\n"
                "/chart EURUSD\n"
                "/chart EURUSD 15 300\n"
                "/chart EURUSD 60 \"2024-08-01 14:30:00\" \"2025-01-01 14:30:00\""
            )
            return

        raw_symbols = context.args[0]
        raw_timeframes = DEFAULT_TIMEFRAME
        outputsize = DEFAULT_OUTPUTSIZE
        from_date = None
        to_date = None

        # initial tokens (everything after the symbol)
        raw_tokens = context.args[1:]
        # merge quoted fragments so quoted date/time stays as one token
        tokens = _merge_quoted_tokens(raw_tokens)

        # helpers
        def parse_positive_int(tok):
            try:
                v = int(tok)
                return v if v > 0 else None
            except Exception:
                return None

        def clean_token(s: str) -> str:
            if not isinstance(s, str):
                return s
            s = s.strip()
            # remove surrounding matching quotes
            if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
                s = s[1:-1].strip()
            # remove stray leading/trailing quotes if any
            s = s.lstrip('"\'').rstrip('"\'').strip()
            return s

        def consume_date(tokens_list, idx):
            """
            Attempt to parse a date starting at tokens_list[idx].
            Supports:
              - single token (cleaned)
              - combined token + next_token (for unquoted "YYYY-MM-DD HH:MM:SS")
            Returns (timestamp_or_None, consumed_count)
            """
            if idx >= len(tokens_list):
                return None, 0

            # try single cleaned token
            t1 = clean_token(tokens_list[idx])
            try:
                ts = to_unix_timestamp(t1)
                return ts, 1
            except Exception:
                # try combine with next token
                if idx + 1 < len(tokens_list):
                    combined = f"{tokens_list[idx]} {tokens_list[idx + 1]}"
                    combined = clean_token(combined)
                    try:
                        ts = to_unix_timestamp(combined)
                        return ts, 2
                    except Exception:
                        return None, 0
                return None, 0

        # parsing index
        i = 0

        # Step A: first token -> timeframe or date (if looks like date)
        if i < len(tokens):
            # quick heuristic: dates usually contain '-' or ':' or 'T' or ','
            cand = tokens[i].strip()
            if any(ch in cand for ch in "-:T,"):
                ts, consumed = consume_date(tokens, i)
                if ts is not None:
                    from_date = ts
                    i += consumed
                else:
                    # fallback to treat as timeframe
                    raw_timeframes = tokens[i]
                    i += 1
            else:
                # treat as timeframe token
                raw_timeframes = tokens[i]
                i += 1

        # Step B: next token -> explicit outputsize or date
        if i < len(tokens):
            maybe_int = parse_positive_int(tokens[i])
            if maybe_int is not None:
                outputsize = maybe_int
                i += 1
            else:
                ts, consumed = consume_date(tokens, i)
                if ts is not None:
                    if from_date is None:
                        from_date = ts
                    else:
                        to_date = ts
                    i += consumed
                else:
                    await update.message.reply_text(
                        "⚠️ Third argument must be either a positive integer (outputsize) or a date (from_date). "
                        "Wrap multi-word dates in quotes (e.g. \"2024-08-01 14:30:00\")."
                    )
                    return

        # Step C: next token -> to_date or outputsize fallback
        if i < len(tokens):
            ts, consumed = consume_date(tokens, i)
            if ts is not None:
                if from_date is None:
                    from_date = ts
                else:
                    to_date = ts
                i += consumed
            else:
                maybe_int = parse_positive_int(tokens[i])
                if maybe_int is not None:
                    outputsize = maybe_int
                    i += 1
                else:
                    await update.message.reply_text(
                        "⚠️ Fourth argument must be to_date (date) or outputsize (positive integer). "
                        "Wrap multi-word dates in quotes (e.g. \"2024-08-01 14:30:00\")."
                    )
                    return

        # leftover tokens -> too many args
        if i < len(tokens):
            await update.message.reply_text("⚠️ Too many arguments. See /chart help for usage.")
            return

        # If any date provided, force outputsize
        if from_date is not None or to_date is not None:
            outputsize = DATE_FORCED_OUTPUTSIZE

        # Normalize symbols/timeframes
        symbols = [s.strip() for s in raw_symbols.split(",") if s.strip()]
        if not symbols:
            await update.message.reply_text("⚠️ No valid symbols provided.")
            return

        raw_tfs = [t.strip() for t in raw_timeframes.split(",") if t.strip()]
        if not raw_tfs:
            await update.message.reply_text("⚠️ No valid timeframes provided.")
            return

        normalized_tfs = []
        try:
            for tf in raw_tfs:
                normalized_tfs.append(normalize_timeframe(tf))
        except Exception as e:
            await update.message.reply_text(f"⚠️ Invalid timeframe '{tf}': {e}")
            return

        await update.message.reply_text(
            f"Generating charts for {len(symbols)} symbol(s) × {len(normalized_tfs)} timeframe(s), "
            f"outputsize={outputsize}. This may take a moment..."
        )

        # generate charts using executor
        loop = asyncio.get_running_loop()
        for symbol in symbols:
            for tf in normalized_tfs:
                try:
                    call = functools.partial(
                        get_chart,
                        symbol=symbol,
                        timeframe=tf,
                        alert_price=None,
                        outputsize=outputsize,
                        from_date=from_date,
                        to_date=to_date
                    )
                    buf, time_frame = await loop.run_in_executor(None, call)
                    buf.seek(0)
                    await update.message.reply_photo(
                        photo=buf,
                        filename=f"{symbol}_{time_frame}.png",
                        caption=f"⏱ Timeframe: {time_frame}, Symbol: {symbol.upper()}"
                    )
                except ValueError as ve:
                    await update.message.reply_text(f"⚠️ {ve}")
                except Exception as e:
                    logger.exception("Error while generating chart")
                    await update.message.reply_text(f"⚠️ Failed to generate chart for {symbol} {tf}: {e}")

                await asyncio.sleep(INTER_CHART_DELAY)

    except Exception as e:
        logger.exception("Unhandled error in chart_command")
        await update.message.reply_text(f"⚠️ Unexpected error: {e}")


handler = CommandHandler("chart", chart_command)
