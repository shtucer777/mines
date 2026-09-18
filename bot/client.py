import asyncio
import logging
from typing import Any

import httpx

from .config import settings

logger = logging.getLogger(__name__)

API_URL = "https://stake.com/_api/graphql"

MINES_BET_MUTATION = """
mutation MinesBet($amount: Float!, $currency: CurrencyEnum!, $minesCount: Int!) {
  minesBet(amount: $amount, currency: $currency, minesCount: $minesCount) {
    id
    active
    payoutMultiplier
    amount
    payout
    state {
      mines
      minesCount
      rounds {
        field
        payoutMultiplier
      }
    }
  }
}
"""

MINES_NEXT_MUTATION = """
mutation MinesNext($id: String!, $field: Int!) {
  minesNext(id: $id, field: $field) {
    id
    active
    payoutMultiplier
    amount
    payout
    state {
      mines
      minesCount
      rounds {
        field
        payoutMultiplier
      }
    }
  }
}
"""

MINES_CASHOUT_MUTATION = """
mutation MinesCashout($id: String!) {
  minesCashout(id: $id) {
    id
    active
    payoutMultiplier
    amount
    payout
    state {
      mines
      minesCount
      rounds {
        field
        payoutMultiplier
      }
    }
  }
}
"""


class StakeClient:
    def __init__(self, token: str | None = None):
        self._token = token or settings.stake_api_token
        self._client: httpx.AsyncClient | None = None
        self._semaphore = asyncio.Semaphore(1)

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "x-access-token": self._token,
            "content-type": "application/json",
            "referer": "https://stake.com/casino/games/mines",
        }

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=self._headers,
                timeout=httpx.Timeout(30.0, connect=10.0),
                http2=True,
                limits=httpx.Limits(
                    max_connections=5,
                    max_keepalive_connections=2,
                ),
            )
        return self._client

    async def _graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        async with self._semaphore:
            client = await self._ensure_client()
            payload = {"query": query, "variables": variables}
            resp = await client.post(API_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()

            if "errors" in data:
                raise StakeAPIError(data["errors"])

            return data["data"]

    async def place_bet(
        self,
        amount: float,
        mines_count: int,
        currency: str = "btc",
    ) -> dict[str, Any]:
        logger.info("Placing bet: %.8f %s, mines=%d", amount, currency, mines_count)
        result = await self._graphql(
            MINES_BET_MUTATION,
            {"amount": amount, "currency": currency, "minesCount": mines_count},
        )
        return result["minesBet"]

    async def reveal_tile(self, game_id: str, field: int) -> dict[str, Any]:
        logger.debug("Revealing tile %d for game %s", field, game_id)
        result = await self._graphql(
            MINES_NEXT_MUTATION,
            {"id": game_id, "field": field},
        )
        return result["minesNext"]

    async def cashout(self, game_id: str) -> dict[str, Any]:
        logger.info("Cashing out game %s", game_id)
        result = await self._graphql(
            MINES_CASHOUT_MUTATION,
            {"id": game_id},
        )
        return result["minesCashout"]

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class StakeAPIError(Exception):
    def __init__(self, errors: list[dict]):
        self.errors = errors
        messages = [e.get("message", str(e)) for e in errors]
        super().__init__("; ".join(messages))
