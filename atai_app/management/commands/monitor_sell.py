from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone
from atai_app.models import Profile, Trade, CoinbaseAccount
import requests
import decimal
import uuid
import json


def fetch_order_summary(oauth_token, order_id, client_order_id):
    url = f"https://api.coinbase.com/api/v3/brokerage/orders/historical/{order_id}?client_order_id={client_order_id}&user_native_currency=EUR"
    headers = {
        'Authorization': f'Bearer {oauth_token}',
        'Content-Type': 'application/json'
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        order_summary = response.json()
        # Fetch fee information
        fee_info = order_summary['order'].get('total_fees', 'Fee information not available')
        # Fetch filled size
        filled_size = order_summary['order'].get('filled_value', 'Filled size not available')
        return fee_info, filled_size
    else:
        print(f"Failed to fetch order summary. Status code: {response.status_code}, Response: {response.text}")
        return None, None


def get_coinbase_prices(currencies, base_currency='EUR'):
    prices = {}
    for currency in currencies:
        # Coinbase API endpoint for current exchange rates for a currency
        api_url = f'https://api.coinbase.com/v2/exchange-rates?currency={currency}'

        try:
            response = requests.get(api_url)
            response.raise_for_status()  # Check for HTTP errors
            data = response.json()

            # Get the exchange rate from the specified currency to the base currency (e.g., 'EUR')
            rate = data['data']['rates'][base_currency]
            prices[currency] = rate
        except requests.RequestException as e:
            print(f"An error occurred while fetching prices for {currency}: {e}")
        except KeyError:
            print(f"Could not find rate for {currency} in response.")

    return prices


def create_sell_order(coinbase_account, product_id, base_size):
    url = "https://api.coinbase.com/api/v3/brokerage/orders"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {coinbase_account.access_token}'
    }
    client_order_id = str(uuid.uuid4())

    payload = json.dumps({
        "client_order_id": client_order_id,
        "product_id": product_id,
        "side": "SELL",
        "order_configuration": {
            "market_market_ioc": {  # Immediate or cancel market order
                "base_size": base_size
            }
        }
    })

    response = requests.post(url, headers=headers, data=payload)
    if response.status_code in [200, 201]:
        print("Order created successfully.")
        response_data = response.json()  # Parse the JSON response
        print(response_data)
        # Extract the order_id from the response, if present
        order_id = response_data.get('success_response', {}).get('order_id', 'No order ID found')
        return True, order_id, client_order_id
    else:
        print(f"Failed to create trade on Coinbase. Status code: {response.status_code}, Response: {response.text}")
        return False, None, None  # Return None for order_id and client_order_id if the request fails


class Command(BaseCommand):
    help = 'Detect any sell positions and execute trades'

    def handle(self, *args, **options):
        prices = get_coinbase_prices(['BTC', 'ETH'])
        print("monitoring sell")
        for trade in Trade.objects.filter(is_active=True):
            profile = trade.profile
            coinbase_account = profile.user.coinbase_account

            current_price = decimal.Decimal(prices.get(trade.coin_type))
            # Check if price matches TP or SL
            if current_price >= trade.take_profit or current_price <= trade.stop_loss:

                product_id = f"{trade.coin_type}-USDC"
                base_size = trade.quantity_coin - Decimal("0.00000001")  # Tolerance for inaccuracy of batch size
                success, order_id, client_order_id = create_sell_order(coinbase_account, product_id, str(base_size))
                print(order_id + " - " + client_order_id)
                if success:
                    fee_info, filled_size = fetch_order_summary(coinbase_account.access_token, order_id,
                                                                client_order_id)
                    trade.is_active = False
                    last_fee = trade.fee_amount
                    trade.fee_amount = last_fee + Decimal(str(fee_info))
                    trade.sell_quantity_usdc = filled_size
                    trade.sell_price = current_price
                    trade.calculate_profit_loss()
                    trade.save()
                    print(f"Trade for {trade.coin_type} completed.")
                else:
                    print(f"Failed to execute sell order for {trade.coin_type}.")
