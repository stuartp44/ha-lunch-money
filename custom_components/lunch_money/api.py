"""
Lunch Money API client for Home Assistant integration.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

import lunchmoney
from lunchmoney.api.manual_accounts_api import ManualAccountsApi
from lunchmoney.api.me_api import MeApi
from lunchmoney.api.plaid_accounts_api import PlaidAccountsApi
from lunchmoney.api.summary_api import SummaryApi
from lunchmoney.api.transactions_bulk_api import TransactionsBulkApi

_LOGGER = logging.getLogger(__name__)

_EXCLUDED_STATUSES = {
    "inactive",
    "not supported",
    "not_found",
    "not found",
    "closed",
    "deactivated",
    "revoked",
    "error",
}


def _coerce_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _normalize_type_name(value: Any) -> str:
    if hasattr(value, "value"):
        value = value.value
    type_name = str(value or "other").replace("_", " ").strip().lower()
    if type_name == "depository":
        type_name = "cash"
    return type_name.title()


def _status_value(value: Any) -> str:
    if hasattr(value, "value"):
        value = value.value
    return str(value or "").strip().lower().replace("_", " ")

class LunchMoneyAPI:
    def __init__(self, api_key):
        self._configuration = lunchmoney.Configuration(access_token=api_key)
        self._client = lunchmoney.ApiClient(self._configuration)
        self._manual_accounts = ManualAccountsApi(self._client)
        self._plaid_accounts = PlaidAccountsApi(self._client)
        self._me = MeApi(self._client)
        self._transactions = TransactionsBulkApi(self._client)
        self._summary = SummaryApi(self._client)

    async def async_close(self) -> None:
        await self._client.close()

    async def async_get_me(self):
        return await self._me.get_me()

    async def _count_transactions(self, **filters: Any) -> int:
        total = 0
        offset = 0
        limit = 2000

        while True:
            response = await self._transactions.get_all_transactions(
                limit=limit,
                offset=offset,
                **filters,
            )
            transactions = response.transactions or []
            count = len(transactions)
            total += count

            if not response.has_more or count == 0:
                break

            offset += count

        return total

    async def _get_current_month_uncategorized_count(self) -> int:
        today = date.today()
        start_date = today.replace(day=1)
        next_month = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        end_date = next_month - timedelta(days=1)

        summary = await self._summary.get_budget_summary(
            start_date=start_date,
            end_date=end_date,
            include_totals=True,
        )

        totals = getattr(summary, "totals", None)
        inflow = getattr(totals, "inflow", None)
        outflow = getattr(totals, "outflow", None)
        inflow_uncategorized = int(getattr(inflow, "uncategorized_count", 0) or 0)
        outflow_uncategorized = int(getattr(outflow, "uncategorized_count", 0) or 0)
        return inflow_uncategorized + outflow_uncategorized

    async def async_get_balances(self):
        """Fetch and group balances from manual and Plaid accounts in v2."""
        grouped = {}

        manual_response = await self._manual_accounts.get_all_manual_accounts()
        for account in manual_response.manual_accounts or []:
            if getattr(account, "closed_on", None):
                continue
            if _status_value(getattr(account, "status", "")) in _EXCLUDED_STATUSES:
                continue

            type_name = _normalize_type_name(getattr(account, "type", "other"))
            balance = _coerce_float(getattr(account, "to_base", 0))
            grouped[type_name] = grouped.get(type_name, 0.0) + balance

        plaid_response = await self._plaid_accounts.get_all_plaid_accounts()
        for account in plaid_response.plaid_accounts or []:
            if _status_value(getattr(account, "status", "")) in _EXCLUDED_STATUSES:
                continue

            type_name = _normalize_type_name(getattr(account, "type", "other"))
            balance = _coerce_float(getattr(account, "to_base", 0))
            grouped[type_name] = grouped.get(type_name, 0.0) + balance

        _LOGGER.debug("Fetched %s grouped Lunch Money account types", len(grouped))
        return grouped

    async def async_get_metrics(self) -> dict[str, int]:
        """Fetch actionable transaction metrics from v2 endpoints."""
        awaiting_review = await self._count_transactions(
            status="unreviewed",
            is_pending=False,
            include_pending=False,
        )
        pending = await self._count_transactions(is_pending=True)
        delete_pending = await self._count_transactions(status="delete_pending")
        uncategorized_month = await self._get_current_month_uncategorized_count()

        return {
            "transactions_awaiting_review": awaiting_review,
            "transactions_pending": pending,
            "transactions_delete_pending": delete_pending,
            "uncategorized_transactions_month": uncategorized_month,
        }

    async def async_get_dashboard_data(self) -> dict[str, dict[str, Any]]:
        """Fetch all sensor data used by the integration."""
        balances, metrics = await asyncio.gather(
            self.async_get_balances(),
            self.async_get_metrics(),
        )
        return {"balances": balances, "metrics": metrics}
