# Lunch Money Home Assistant Integration

This custom integration exposes your Lunch Money account types (e.g., Cash, Credit, etc.) as Home Assistant sensor entities.

It uses Lunch Money API v2 and the official async Python client (`lunchmoney-python-async`).

## Notes

1. Lunch Money v2 is currently marked as open alpha by Lunch Money.
2. This integration groups balances by account type using manual accounts and Plaid accounts.
3. Accounts in inactive/error-like states are excluded from totals.
4. Integration startup performs an API readiness check and raises `ConfigEntryNotReady` before platform forwarding if Lunch Money is temporarily unavailable.
5. Manual/Plaid account parsing includes a fallback path for schema-inconsistent records returned by the API.

## Sensors

1. Balance by account type (for example: Cash, Credit, Investment).
2. Transactions Awaiting Review.
3. Pending Transactions.
4. Transactions Delete Pending (requires manual intervention).
5. Uncategorized Transactions (This Month).
6. Net Income (This Month).
7. Savings Rate (This Month).
8. Last Transaction.
9. Balance sensors use type-based icons (for example, Cash uses a cash icon).

## Installation

### HACS (Recommended)

1. Go to **HACS > Integrations** in your Home Assistant UI.
2. Click the three dots in the top right and select **Custom repositories**.
3. Add this repository's URL and select **Integration** as the category.
4. Search for "Lunch Money" in HACS and install the integration.
5. Restart Home Assistant.
6. Go to **Settings > Devices & Services > Add Integration** and search for "Lunch Money".
7. Enter your Lunch Money API key when prompted.

### Manual

1. Copy the `lunch_money` folder into your Home Assistant `custom_components` directory:
   - Example: `/config/custom_components/lunch_money`
2. Restart Home Assistant.
3. In Home Assistant UI, go to **Settings > Devices & Services > Add Integration** and search for "Lunch Money".
4. Enter your Lunch Money API key when prompted.

## Requirements

1. A valid Lunch Money developer API token.
2. Home Assistant with internet access to `api.lunchmoney.dev`.
