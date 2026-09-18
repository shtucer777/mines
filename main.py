#!/usr/bin/env python3
"""
Mines betting automation bot.

Lightweight HTTP client — no browser JS overhead.
Direct GraphQL calls to Stake API with rate limiting.
"""

import argparse
import asyncio
import json
import logging
import sys

from bot.config import settings
from bot.client import StakeClient
from bot.mines_bot import MinesBot
from bot.strategies import STRATEGIES, get_strategy
from bot.multi_bot import MultiBotRunner, MultiBotConfig


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Mines betting bot")

    sub = p.add_subparsers(dest="command", required=True)

    # Single bot
    single = sub.add_parser("run", help="Run a single bot")
    single.add_argument("--amount", type=float, help="Bet amount")
    single.add_argument("--mines", type=int, help="Number of mines (1-24)")
    single.add_argument("--rounds", type=int, help="Max rounds to play")
    single.add_argument("--delay", type=float, help="Delay between bets (seconds)")
    single.add_argument(
        "--strategy",
        choices=list(STRATEGIES),
        help="Betting strategy",
    )
    single.add_argument("-v", "--verbose", action="store_true")

    # Multi bot
    multi = sub.add_parser("multi", help="Run multiple bots in parallel")
    multi.add_argument("config_file", help="JSON config file with bot definitions")
    multi.add_argument("-v", "--verbose", action="store_true")

    # Dry run — test connection
    test = sub.add_parser("test", help="Test API connection")
    test.add_argument("-v", "--verbose", action="store_true")

    # List strategies
    sub.add_parser("strategies", help="List available strategies")

    return p.parse_args()


async def cmd_run(args: argparse.Namespace) -> None:
    strategy = get_strategy(args.strategy or settings.strategy)
    client = StakeClient()
    bot = MinesBot(client=client, strategy=strategy)

    await bot.run(
        max_rounds=args.rounds,
        bet_amount=args.amount,
        mines_count=args.mines,
        delay=args.delay,
    )


async def cmd_multi(args: argparse.Namespace) -> None:
    with open(args.config_file) as f:
        raw = json.load(f)

    configs = [MultiBotConfig(**entry) for entry in raw["bots"]]
    runner = MultiBotRunner(configs)
    await runner.run_all()


async def cmd_test(_args: argparse.Namespace) -> None:
    client = StakeClient()
    try:
        logging.info("Testing API connection...")
        result = await client.place_bet(0.0, 1)
        logging.info("Connection OK: %s", result)
    except Exception as e:
        logging.error("Connection failed: %s", e)
        sys.exit(1)
    finally:
        await client.close()


def cmd_strategies() -> None:
    print("Available strategies:")
    for name, cls in STRATEGIES.items():
        doc = cls.__doc__ or ""
        print(f"  {name:15s} — {doc.strip()}")


def main() -> None:
    args = parse_args()

    if args.command == "strategies":
        cmd_strategies()
        return

    setup_logging(getattr(args, "verbose", False))

    if args.command == "run":
        asyncio.run(cmd_run(args))
    elif args.command == "multi":
        asyncio.run(cmd_multi(args))
    elif args.command == "test":
        asyncio.run(cmd_test(args))


if __name__ == "__main__":
    main()
