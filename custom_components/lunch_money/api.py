"""
Lunch Money API client for Home Assistant integration.
"""
from __future__ import annotations

import asyncio
import json
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


def _field_value(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


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


def _month_bounds(target_date: date) -> tuple[date, date]:
    start_date = target_date.replace(day=1)
    next_month = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
    end_date = next_month - timedelta(days=1)
    return start_date, end_date


def _activity_total(breakdown: Any) -> float:
    if breakdown is None:
        return 0.0

    return (
        _coerce_float(getattr(breakdown, "other_activity", 0))
        + _coerce_float(getattr(breakdown, "recurring_activity", 0))
        + _coerce_float(getattr(breakdown, "uncategorized", 0))
        + _coerce_float(getattr(breakdown, "uncategorized_recurring", 0))
    )

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

    async def async_get_currency(self) -> str:
        user = await self.async_get_me()
        currency = getattr(user, "primary_currency", None)
        if hasattr(currency, "value"):
            currency = currency.value
        return str(currency or "USD").upper()

    def _decode_raw_json(self, response: Any) -> dict[str, Any]:
        payload = getattr(response, "data", response)

        if isinstance(payload, (bytes, bytearray)):
            payload = payload.decode("utf-8")

        if isinstance(payload, str):
            return json.loads(payload) if payload else {}

        if isinstance(payload, dict):
            return payload

        return {}

    async def _get_accounts_safe(
        self,
        fetch_typed,
        fetch_raw,
        payload_key: str,
        source_name: str,
    ) -> list[Any]:
        try:
            response = await fetch_typed()
            return getattr(response, payload_key) or []
        except Exception as err:
            _LOGGER.warning(
                "Falling back to raw %s parsing due to schema mismatch: %s",
                source_name,
                err,
            )
            raw_response = await fetch_raw()
            payload = self._decode_raw_json(raw_response)
            items = payload.get(payload_key)
            return items if isinstance(items, list) else []

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

    async def _get_current_month_summary_metrics(self) -> dict[str, float]:
        today = date.today()
        start_date, end_date = _month_bounds(today)

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

        inflow_total = _activity_total(inflow)
        outflow_total = _activity_total(outflow)
        net_income = inflow_total - outflow_total
        savings_rate = (net_income / inflow_total * 100.0) if inflow_total > 0 else 0.0

        return {
            "uncategorized_transactions_month": inflow_uncategorized + outflow_uncategorized,
            "net_income_month": round(net_income, 2),
            "savings_rate_month": round(savings_rate, 2),
        }

    async def _get_last_transaction_metric(self) -> dict[str, Any]:
        response = await self._transactions.get_all_transactions(
            limit=1,
            include_pending=True,
        )
        transactions = response.transactions or []
        if not transactions:
            return {
                "state": "No transactions",
                "attributes": {},
            }

        tx = transactions[0]
        date_value = getattr(tx, "var_date", None)
        date_text = date_value.isoformat() if hasattr(date_value, "isoformat") else str(date_value)
        payee = getattr(tx, "payee", None) or "Unknown Payee"
        amount_base = _coerce_float(getattr(tx, "to_base", getattr(tx, "amount", 0)))

        return {
            "state": payee,
            "attributes": {
                "id": getattr(tx, "id", None),
                "date": date_text,
                "amount": _coerce_float(getattr(tx, "amount", 0)),
                "to_base": amount_base,
                "currency": str(getattr(tx, "currency", "")),
                "status": getattr(tx, "status", None),
                "is_pending": getattr(tx, "is_pending", None),
                "category_id": getattr(tx, "category_id", None),
                "manual_account_id": getattr(tx, "manual_account_id", None),
                "plaid_account_id": getattr(tx, "plaid_account_id", None),
                "updated_at": str(getattr(tx, "updated_at", "")),
            },
        }

    async def async_get_balances(self):
        """Fetch and group balances from manual and Plaid accounts in v2."""
        grouped = {}

        manual_accounts = await self._get_accounts_safe(
            self._manual_accounts.get_all_manual_accounts,
            self._manual_accounts.get_all_manual_accounts_without_preload_content,
            "manual_accounts",
            "manual account",
        )
        for account in manual_accounts:
            if _field_value(account, "closed_on", None):
                continue
            if _status_value(_field_value(account, "status", "")) in _EXCLUDED_STATUSES:
                continue

            type_name = _normalize_type_name(_field_value(account, "type", "other"))
            balance = _coerce_float(_field_value(account, "to_base", 0))
            grouped[type_name] = grouped.get(type_name, 0.0) + balance

        plaid_accounts = await self._get_accounts_safe(
            self._plaid_accounts.get_all_plaid_accounts,
            self._plaid_accounts.get_all_plaid_accounts_without_preload_content,
            "plaid_accounts",
            "plaid account",
        )
        for account in plaid_accounts:
            if _status_value(_field_value(account, "status", "")) in _EXCLUDED_STATUSES:
                continue

            type_name = _normalize_type_name(_field_value(account, "type", "other"))
            balance = _coerce_float(_field_value(account, "to_base", 0))
            grouped[type_name] = grouped.get(type_name, 0.0) + balance

        _LOGGER.debug("Fetched %s grouped Lunch Money account types", len(grouped))
        return grouped

    async def async_get_metrics(self) -> dict[str, float]:
        """Fetch actionable transaction metrics from v2 endpoints."""
        awaiting_review = await self._count_transactions(
            status="unreviewed",
            is_pending=False,
            include_pending=False,
        )
        pending = await self._count_transactions(is_pending=True)
        delete_pending = await self._count_transactions(status="delete_pending")
        month_summary_metrics = await self._get_current_month_summary_metrics()
        last_transaction = await self._get_last_transaction_metric()

        return {
            "transactions_awaiting_review": awaiting_review,
            "transactions_pending": pending,
            "transactions_delete_pending": delete_pending,
            "uncategorized_transactions_month": month_summary_metrics["uncategorized_transactions_month"],
            "net_income_month": month_summary_metrics["net_income_month"],
            "savings_rate_month": month_summary_metrics["savings_rate_month"],
            "last_transaction": last_transaction,
        }

    async def async_get_dashboard_data(self) -> dict[str, dict[str, Any]]:
        """Fetch all sensor data used by the integration."""
        currency, balances, metrics = await asyncio.gather(
            self.async_get_currency(),
            self.async_get_balances(),
            self.async_get_metrics(),
        )
        return {"currency": currency, "balances": balances, "metrics": metrics}
