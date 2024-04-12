from django.conf import settings
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
import csv
from atai_app.models import Profile, Trade, CoinbaseAccount
from decimal import Decimal
import requests
import uuid
import json
from django.utils import timezone
from datetime import datetime
from keras.models import load_model
from joblib import load
import pandas_ta as ta
import pandas as pd
import ccxt


# --------------------------------------------------------------------
def btc_get_buy_signal_probability(self):
    def btc_fetch_recent_data(symbol, number_of_candles=165, timeframe='30m'):
        exchange = ccxt.binance()
        milliseconds_per_candle = 1800000  # 30 minutes
        since = exchange.milliseconds() - milliseconds_per_candle * number_of_candles
        candles = exchange.fetch_ohlcv(symbol, timeframe, since, number_of_candles)
        df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df

    def btc_get_fear_and_greed_index():
        response = requests.get("https://api.alternative.me/fng/")
        data = response.json()
        return data['data'][0]['value']

    def get_bitcoin_dominance():
        response = requests.get("https://api.coingecko.com/api/v3/global")
        data = response.json()
        return data['data']['market_cap_percentage']['btc'] / 100

    def btc_calculate_indicators(df):
        df['SMA'] = ta.sma(df['close'], length=150)
        df['RSI'] = ta.rsi(df['close'], length=14)
        df['OBV'] = ta.obv(df['close'], df['volume'])
        df['ATR'] = ta.atr(df['high'], df['low'], df['close'])
        return df

    def btc_calculate_all_signals(df, ma_backcandles, obv_backcandles, obv_threshold, atr_backcandles, atr_threshold):
        # print("Calculating All Signals")
        # Initialize signal and change lists
        obv_signal = [0] * len(df)
        obv_relative_change = [0] * len(df)
        atr_signal = [0] * len(df)
        atr_relative_change = [0] * len(df)
        sma_signal = [0] * len(df)

        # Loop through the DataFrame once
        for row in range(1, len(df)):
            # OBV calculations
            if row >= obv_backcandles and df.OBV[row - obv_backcandles] != 0:
                obv_relative = (df.OBV[row] - df.OBV[row - obv_backcandles]) / abs(df.OBV[row - obv_backcandles])
                obv_relative_change[row] = obv_relative
                obv_signal[row] = 2 if obv_relative > obv_threshold else 0 if obv_relative < -obv_threshold else 1

            # ATR calculations
            if row >= atr_backcandles and df.ATR[row - atr_backcandles] != 0:
                atr_relative = (df.ATR[row] - df.ATR[row - atr_backcandles]) / abs(df.ATR[row - atr_backcandles])
                atr_relative_change[row] = atr_relative
                atr_signal[row] = 2 if atr_relative > atr_threshold else 0 if atr_relative < -atr_threshold else 1

            # SMA calculations
            if row >= ma_backcandles:
                sma_uptrend = any(
                    df.open[i] >= df.SMA[i] and df.close[i] >= df.SMA[i] for i in range(row - ma_backcandles, row))
                sma_downtrend = any(
                    df.open[i] < df.SMA[i] and df.close[i] < df.SMA[i] for i in range(row - ma_backcandles, row))
                sma_signal[
                    row] = 2 if sma_uptrend and not sma_downtrend else 0 if sma_downtrend and not sma_uptrend else 1

        # Assign calculated lists to DataFrame
        df['OBVSignal'] = obv_signal
        df['OBVRelativeChange'] = obv_relative_change
        df['ATRSignal'] = atr_signal
        df['ATRRelativeChange'] = atr_relative_change
        df['SMASignal'] = sma_signal

        return df

    # Load models
    xgboost_model = load('atai_app/management/commands/binary_btc_xgboost_model_10k.joblib')
    lstm_model = load_model('atai_app/management/commands/new_binary_btc_LSTM_model_10k.keras')
    meta_model = load('atai_app/management/commands/meta_learner_10k.joblib')

    # Candles
    backcandles = 15
    obv_backcandles = 150
    obv_threshold = 0.015
    atr_backcandles = backcandles
    atr_threshold = 0.05

    # Fetch live data
    btc_data = btc_fetch_recent_data('BTC/USDT')
    btc_data = btc_calculate_indicators(btc_data)
    df = btc_calculate_all_signals(btc_data, backcandles, obv_backcandles, obv_threshold, atr_backcandles,
                                   atr_threshold)

    fear_and_greed_index = btc_get_fear_and_greed_index()
    bitcoin_dominance = get_bitcoin_dominance()

    # Preprocess data
    data = {
        'RSI': btc_data.RSI.iloc[-1],
        'fear_and_greed_index': int(fear_and_greed_index),
        'dominance': bitcoin_dominance,
        'SMASignal': btc_data.SMASignal.iloc[-1],
        'OBV': btc_data.OBV.iloc[-1],
        'ATR': btc_data.ATR.iloc[-1],
        'OBVSignal': btc_data.OBVSignal.iloc[-1],
        'OBVRelativeChange': btc_data.OBVRelativeChange.iloc[-1],
        'ATRSignal': btc_data.ATRSignal.iloc[-1],
        'ATRRelativeChange': btc_data.ATRRelativeChange.iloc[-1],
    }

    # print(btc_data.iloc[0].name)
    # print(data)

    # Initialise df
    xg_attributes = ['RSI', 'fear_and_greed_index', 'dominance', 'SMASignal', 'OBV', 'ATR']
    xg_df = pd.DataFrame([data])[xg_attributes]
    lstm_attributes = ['RSI', 'fear_and_greed_index', 'dominance', 'SMASignal', 'OBVSignal', 'OBVRelativeChange',
                       'ATRSignal', 'ATRRelativeChange']
    lstm_df = pd.DataFrame([data])[lstm_attributes]

    # Scale features for XGBoost and LSTM
    attributes = ['RSI', 'fear_and_greed_index', 'dominance', 'SMASignal', 'OBV', 'ATR']
    scaler_xgb = load('atai_app/management/commands/xgboost_scaler.joblib')
    scaler_lstm = load('atai_app/management/commands/new_minmax_lstm_scaler.joblib')
    # XGBoost
    xg_df['RSI'] /= 100
    xg_df['fear_and_greed_index'] /= 100
    features_to_scale_xgb = ['OBV', 'ATR']
    xg_df[features_to_scale_xgb] = scaler_xgb.transform(xg_df[features_to_scale_xgb])
    # Make sure lstm_attributes matches the model's expected input features
    scaled_lstm = scaler_lstm.transform(lstm_df)
    scaled_lstm = scaled_lstm.reshape(scaled_lstm.shape[0], 1, scaled_lstm.shape[1])

    # # Predict with XGBoost and LSTM
    # xgb_proba = xgboost_model.predict_proba(xg_df)[:, 1]
    # lstm_proba = lstm_model.predict(scaled_lstm)[:, 0]  # Adjusted for the sigmoid output
    #
    # # Prepare meta-features and predict with meta-learner
    # meta_features = np.column_stack([xgb_proba, lstm_proba])
    # meta_predictions = meta_model.predict(meta_features)
    # meta_proba = meta_model.predict_proba(meta_features)
    #
    # # Print the results
    # print(f"Latest data at: {xg_df.index[0]}")
    # print(f"Predicted class by Meta Model: {meta_predictions[0]}")
    # print(f"Probability distribution (Class '0', Class '1'): {meta_proba[0]}")
    #
    # # Determine if it's a buy signal based on Meta Model
    # is_buy_signal = meta_predictions[0] == 1
    # buy_signal_probability = meta_proba[0][1]
    # print(meta_proba[0])
    # print(f"Is it a buy signal? {is_buy_signal}")
    # print(f"Probability of being a buy signal (Class '1'): {buy_signal_probability:.4f}")
    #
    # print(xgb_proba, lstm_proba)
    # print(meta_predictions, meta_proba)

    # Assume you have the predicted probabilities from XGBoost and LSTM models
    xgb_proba = xgboost_model.predict_proba(xg_df)[:, 1]
    lstm_proba = lstm_model.predict(scaled_lstm)[:, 0]  # Adjusted for the sigmoid output

    # Define your weights for the averaging
    weights = {'xgboost': 0.5, 'lstm': 0.5}

    # Calculate the weighted average of the predicted probabilities
    weighted_avg_proba = (weights['xgboost'] * xgb_proba) + (weights['lstm'] * lstm_proba)

    # Apply a threshold to the averaged probabilities to classify as buy (1) or not buy (0)
    threshold = 0.6  # Adjust the threshold as needed
    weighted_predictions = (weighted_avg_proba >= threshold).astype(int)

    # Print the results based on the weighted averaging method
    # print(f"Latest data at: {xg_df.index[-1]}")  # Assuming you want to print the date of the latest prediction
    # print("Weighted Averaging Predictions:", weighted_predictions)

    # Determine if the latest prediction is a buy signal
    is_buy_signal = weighted_predictions[-1] == 1  # Check the last prediction
    buy_signal_probability = weighted_avg_proba[-1]  # Probability of the last prediction
    # print(f"Is it a buy signal? {is_buy_signal}")
    # print(f"Probability of being a buy signal (Class '1'): {buy_signal_probability:.4f}")
    return buy_signal_probability


# ------------------------------------------------------------------


# --------------------------------------------------------------------
def eth_get_buy_signal_probability(self):
    def eth_fetch_recent_data(symbol, number_of_candles=165, timeframe='30m'):
        exchange = ccxt.binance()
        milliseconds_per_candle = 1800000  # 30 minutes
        since = exchange.milliseconds() - milliseconds_per_candle * number_of_candles
        candles = exchange.fetch_ohlcv(symbol, timeframe, since, number_of_candles)
        df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df

    def eth_get_fear_and_greed_index():
        response = requests.get("https://api.alternative.me/fng/")
        data = response.json()
        return data['data'][0]['value']

    def get_eth_dominance():
        response = requests.get("https://api.coingecko.com/api/v3/global")
        data = response.json()
        return data['data']['market_cap_percentage']['eth'] / 100

    def eth_calculate_indicators(df):
        df['SMA'] = ta.sma(df['close'], length=150)
        df['EMA_fast'] = ta.ema(df['close'], length=30)
        df['EMA_slow'] = ta.ema(df['close'], length=150)
        df['RSI'] = ta.rsi(df['close'], length=14)
        df['OBV'] = ta.obv(df['close'], df['volume'])
        df['ATR'] = ta.atr(df['high'], df['low'], df['close'])
        df['MACD'] = df.ta.macd(close='close', fast=12, slow=26, signal=9)['MACD_12_26_9']
        df['Stoch'] = df.ta.stoch(high='high', low='low', close='close', k=14, d=3)['STOCHk_14_3_3']
        return df

    def eth_calculate_all_signals(df, ma_backcandles, obv_backcandles, obv_threshold, atr_backcandles, atr_threshold):
        obv_signal = [0] * len(df)
        obv_relative_change = [0] * len(df)
        atr_signal = [0] * len(df)
        atr_relative_change = [0] * len(df)
        sma_signal = [0] * len(df)
        ema_signal = [0] * len(df)

        # Loop through the DataFrame once
        for row in range(1, len(df)):
            # OBV calculations
            if row >= obv_backcandles and df.OBV[row - obv_backcandles] != 0:
                obv_relative = (df.OBV[row] - df.OBV[row - obv_backcandles]) / abs(df.OBV[row - obv_backcandles])
                obv_relative_change[row] = obv_relative
                obv_signal[row] = 2 if obv_relative > obv_threshold else 0 if obv_relative < -obv_threshold else 1

            # ATR calculations
            if row >= atr_backcandles and df.ATR[row - atr_backcandles] != 0:
                atr_relative = (df.ATR[row] - df.ATR[row - atr_backcandles]) / abs(df.ATR[row - atr_backcandles])
                atr_relative_change[row] = atr_relative
                atr_signal[row] = 2 if atr_relative > atr_threshold else 0 if atr_relative < -atr_threshold else 1

            # SMA calculations
            if row >= ma_backcandles:
                sma_uptrend = any(
                    df.open[i] >= df.SMA[i] and df.close[i] >= df.SMA[i] for i in range(row - ma_backcandles, row))
                sma_downtrend = any(
                    df.open[i] < df.SMA[i] and df.close[i] < df.SMA[i] for i in range(row - ma_backcandles, row))
                sma_signal[
                    row] = 2 if sma_uptrend and not sma_downtrend else 0 if sma_downtrend and not sma_uptrend else 1

                # EMA calculations (adjusted for EMA_fast and EMA_slow comparison)
                if row >= ma_backcandles:
                    ema_uptrend = all(df.EMA_fast[i] >= df.EMA_slow[i] for i in range(row - ma_backcandles, row))
                    ema_downtrend = all(df.EMA_fast[i] < df.EMA_slow[i] for i in range(row - ma_backcandles, row))
                    ema_signal[
                        row] = 2 if ema_uptrend and not ema_downtrend else 0 if ema_downtrend and not ema_uptrend else 1

        # Assign calculated lists to DataFrame
        df['OBVSignal'] = obv_signal
        df['OBVRelativeChange'] = obv_relative_change
        df['ATRSignal'] = atr_signal
        df['ATRRelativeChange'] = atr_relative_change
        df['SMASignal'] = sma_signal
        df['EMASignal'] = ema_signal

        return df

    # Load models
    xgboost_model = load('atai_app/management/commands/binary_eth_xgboost_model_10k.joblib')
    lstm_model = load_model('atai_app/management/commands/eth_LSTM_model_10k.keras')
    meta_model = load('atai_app/management/commands/eth_meta_learner_10k.joblib')

    # Candles
    backcandles = 15
    obv_backcandles = 150
    obv_threshold = 0.015
    atr_backcandles = backcandles
    atr_threshold = 0.05

    # Fetch live data
    eth_data = eth_fetch_recent_data('BTC/USDT')
    eth_data = eth_calculate_indicators(eth_data)
    df = eth_calculate_all_signals(eth_data, backcandles, obv_backcandles, obv_threshold, atr_backcandles,
                                   atr_threshold)

    fear_and_greed_index = eth_get_fear_and_greed_index()
    eth_domanince = get_eth_dominance()

    # Preprocess data
    data = {
        'RSI': eth_data.RSI.iloc[-1],
        'fear_and_greed_index': int(fear_and_greed_index),
        'dominance': eth_domanince,
        'SMASignal': eth_data.SMASignal.iloc[-1],
        'EMASignal': eth_data.EMASignal.iloc[-1],
        'OBV': eth_data.OBV.iloc[-1],
        'ATR': eth_data.ATR.iloc[-1],
        'MACD': eth_data.MACD.iloc[-1],
        'Stoch': eth_data.Stoch.iloc[-1],
        'OBVSignal': eth_data.OBVSignal.iloc[-1],
        'OBVRelativeChange': eth_data.OBVRelativeChange.iloc[-1],
        'ATRSignal': eth_data.ATRSignal.iloc[-1],
        'ATRRelativeChange': eth_data.ATRRelativeChange.iloc[-1],
    }

    # print(data)

    # Initialise df
    xg_attributes = ['fear_and_greed_index', 'dominance', 'RSI', 'MACD', 'Stoch', 'ATR', 'ATRRelativeChange',
                     'OBVRelativeChange']
    xg_df = pd.DataFrame([data])[xg_attributes]
    lstm_attributes = ['fear_and_greed_index', 'dominance', 'RSI', 'EMASignal', 'SMASignal', 'MACD', 'Stoch',
                       'OBVSignal', 'OBVRelativeChange', 'ATRSignal', 'ATRRelativeChange']
    lstm_df = pd.DataFrame([data])[lstm_attributes]

    # Scale features for XGBoost and LSTM
    attributes = ['RSI', 'fear_and_greed_index', 'dominance', 'SMASignal', 'OBV', 'ATR']
    scaler_xgb = load('atai_app/management/commands/eth_xgboost_scaler.joblib')
    scaler_lstm = load('atai_app/management/commands/eth_lstm_scaler.joblib')
    # XGBoost
    xg_df['RSI'] /= 100
    xg_df['fear_and_greed_index'] /= 100
    features_to_scale_xgb = ['ATR', 'MACD']
    xg_df[features_to_scale_xgb] = scaler_xgb.transform(xg_df[features_to_scale_xgb])
    # Make sure lstm_attributes matches the model's expected input features
    scaled_lstm = scaler_lstm.transform(lstm_df)
    scaled_lstm = scaled_lstm.reshape(scaled_lstm.shape[0], 1, scaled_lstm.shape[1])

    # # Predict with XGBoost and LSTM
    # xgb_proba = xgboost_model.predict_proba(xg_df)[:, 1]
    # lstm_proba = lstm_model.predict(scaled_lstm)[:, 0]  # Adjusted for the sigmoid output
    #
    # # Prepare meta-features and predict with meta-learner
    # meta_features = np.column_stack([xgb_proba, lstm_proba])
    # meta_predictions = meta_model.predict(meta_features)
    # meta_proba = meta_model.predict_proba(meta_features)
    #
    # # Print the results
    # print(f"Latest data at: {xg_df.index[0]}")
    # print(f"Predicted class by Meta Model: {meta_predictions[0]}")
    # print(f"Probability distribution (Class '0', Class '1'): {meta_proba[0]}")
    #
    # # Determine if it's a buy signal based on Meta Model
    # is_buy_signal = meta_predictions[0] == 1
    # buy_signal_probability = meta_proba[0][1]
    # print(meta_proba[0])
    # print(f"Is it a buy signal? {is_buy_signal}")
    # print(f"Probability of being a buy signal (Class '1'): {buy_signal_probability:.4f}")
    #
    # print(xgb_proba, lstm_proba)
    # print(meta_predictions, meta_proba)

    # Assume you have the predicted probabilities from XGBoost and LSTM models
    xgb_proba = xgboost_model.predict_proba(xg_df)[:, 1]
    lstm_proba = lstm_model.predict(scaled_lstm)[:, 0]  # Adjusted for the sigmoid output

    # Define your weights for the averaging
    weights = {'xgboost': 0.5, 'lstm': 0.5}

    # Calculate the weighted average of the predicted probabilities
    weighted_avg_proba = (weights['xgboost'] * xgb_proba) + (weights['lstm'] * lstm_proba)

    # Apply a threshold to the averaged probabilities to classify as buy (1) or not buy (0)
    threshold = 0.6  # Adjust the threshold as needed
    weighted_predictions = (weighted_avg_proba >= threshold).astype(int)

    # Print the results based on the weighted averaging method
    # print(f"Latest data at: {xg_df.index[-1]}")  # Assuming you want to print the date of the latest prediction
    # print("Weighted Averaging Predictions:", weighted_predictions)

    # Determine if the latest prediction is a buy signal
    is_buy_signal = weighted_predictions[-1] == 1  # Check the last prediction
    buy_signal_probability = weighted_avg_proba[-1]  # Probability of the last prediction
    # print(f"Is it a buy signal? {is_buy_signal}")
    # print(f"Probability of being a buy signal (Class '1'): {buy_signal_probability:.4f}")
    return buy_signal_probability


# ------------------------------------------------------------------


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
        filled_size = order_summary['order'].get('filled_size', 'Filled size not available')
        return fee_info, filled_size
    else:
        print(f"Failed to fetch order summary. Status code: {response.status_code}, Response: {response.text}")
        return None, None


def refresh_coinbase_token(coinbase_account):
    refresh_url = 'https://api.coinbase.com/oauth/token'
    refresh_data = {
        'grant_type': 'refresh_token',
        'refresh_token': coinbase_account.refresh_token,
        'client_id': settings.COINBASE_CLIENT_ID,
        'client_secret': settings.COINBASE_CLIENT_SECRET,
    }
    response = requests.post(refresh_url, data=refresh_data)
    if response.status_code == 200:
        token_info = response.json()
        expires_in = timezone.now() + timezone.timedelta(seconds=token_info['expires_in'])
        # Update the CoinbaseAccount instance with the new access and refresh tokens
        CoinbaseAccount.objects.filter(user=coinbase_account.user).update(
            access_token=token_info['access_token'],
            refresh_token=token_info['refresh_token'],
            expires_in=expires_in
        )
    else:
        raise Exception("Failed to refresh Coinbase access token.")


def get_coinbase_price(currency, base_currency='EUR'):
    price = 0
    api_url = f'https://api.coinbase.com/v2/exchange-rates?currency={currency}'
    try:
        response = requests.get(api_url)
        response.raise_for_status()  # Check for HTTP errors
        data = response.json()

        rate = data['data']['rates'][base_currency]
        price = rate
    except requests.RequestException as e:
        print(f"An error occurred while fetching prices for {currency}: {e}")
    except KeyError:
        print(f"Could not find rate for {currency} in response.")
    return price


def create_trade_on_coinbase(coinbase_account, product_id, quote_size):
    url = "https://api.coinbase.com/api/v3/brokerage/orders"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {coinbase_account.access_token}'
    }
    client_order_id = str(uuid.uuid4())  # Generate a unique client_order_id

    payload = json.dumps({
        "client_order_id": client_order_id,
        "product_id": product_id,
        "side": "BUY",
        "order_configuration": {
            "market_market_ioc": {
                "quote_size": quote_size
            }
        }
    })

    response = requests.post(url, headers=headers, data=payload)

    if response.status_code in [200, 201]:
        print("Order created successfully.")
        response_data = response.json()
        # Get the order_id from the response
        order_id = response_data.get('success_response', {}).get('order_id', 'No order ID found')
        return True, order_id, client_order_id
    else:
        print(f"Failed to create trade on Coinbase. Status code: {response.status_code}, Response: {response.text}")
        return False, None, None  # Return None for order_id and client_order_id if the request fails


class Command(BaseCommand):
    help = 'Executes trades based on buy signal probability'

    def handle(self, *args, **options):
        btc_buy_signal_probability = btc_get_buy_signal_probability(self)
        eth_buy_signal_probability = eth_get_buy_signal_probability(self)

        if btc_buy_signal_probability > 0.8 or eth_buy_signal_probability > 0.8:
            for user in User.objects.filter(profile__coinbase_connected=True).all():
                profile = user.profile
                coinbase_account = user.coinbase_account

                # Check if the user is not in a current position
                if not Trade.objects.filter(profile=profile, is_active=True).exists():
                    # Map risk tolerance to buy signal probability thresholds
                    risk_tolerance_thresholds = {0: 0.9, 1: 0.85, 2: 0.8}
                    # Map risk tolerance to TP and SL
                    risk_tolerance_tp_sl = {
                        0: {'TP': 1.03, 'SL': 0.98},
                        1: {'TP': 1.04, 'SL': 0.97},
                        2: {'TP': 1.05, 'SL': 0.96},
                    }

                    risk_tolerance = profile.risk_tolerance
                    threshold = risk_tolerance_thresholds[risk_tolerance]
                    tp_sl_values = risk_tolerance_tp_sl[risk_tolerance]

                    # Check if probability matches risk tolerance
                    if btc_buy_signal_probability > threshold or eth_buy_signal_probability > threshold:

                        # Refresh token if necessary
                        if coinbase_account.expires_in <= timezone.now():
                            refresh_coinbase_token(coinbase_account)

                        # If users trade both coins
                        if profile.trade_btc == True and profile.trade_eth == True:
                            if btc_buy_signal_probability > eth_buy_signal_probability:  # Buy BTC if higher probability
                                print(get_coinbase_price('BTC'))
                                buy_price = Decimal(str(get_coinbase_price('BTC')))

                                quote_size = profile.trade_quantity
                                tp_price = buy_price * Decimal(tp_sl_values['TP'])
                                sl_price = buy_price * Decimal(tp_sl_values['SL'])
                                product_id = "BTC-USDC"
                                # Create trade on Coinbase
                                success, order_id, client_order_id = create_trade_on_coinbase(coinbase_account,
                                                                                              product_id,
                                                                                              str(quote_size))
                                if success:
                                    fee_info, filled_size = fetch_order_summary(coinbase_account.access_token, order_id,
                                                                                client_order_id)
                                    # Add trade
                                    Trade.objects.create(
                                        profile=profile,
                                        coin_type='BTC',
                                        is_active=True,
                                        buy_price=float(buy_price),
                                        quantity_usdc=quote_size,
                                        quantity_coin=filled_size,
                                        stop_loss=sl_price,
                                        fee_amount=fee_info,
                                        take_profit=tp_price
                                    )


                            elif eth_buy_signal_probability > btc_buy_signal_probability:  # Buy ETH if higher probability
                                print(get_coinbase_price('ETH'))
                                buy_price = Decimal(str(get_coinbase_price('ETH')))

                                quote_size = profile.trade_quantity
                                tp_price = buy_price * Decimal(tp_sl_values['TP'])
                                sl_price = buy_price * Decimal(tp_sl_values['SL'])
                                product_id = "ETH-USDC"
                                # Create trade on Coinbase
                                success, order_id, client_order_id = create_trade_on_coinbase(coinbase_account,
                                                                                              product_id,
                                                                                              str(quote_size))
                                if success:
                                    fee_info, filled_size = fetch_order_summary(coinbase_account.access_token, order_id,
                                                                                client_order_id)
                                    # Log the trade in your Django app
                                    Trade.objects.create(
                                        profile=profile,
                                        coin_type='ETH',  # Assuming BTC trades for simplicity
                                        is_active=True,
                                        buy_price=float(buy_price),
                                        quantity_usdc=quote_size,
                                        quantity_coin=filled_size,
                                        stop_loss=sl_price,
                                        fee_amount=fee_info,
                                        take_profit=tp_price
                                    )

                        # If users only trade BTC
                        if profile.trade_btc == True and profile.trade_eth == False:
                            if btc_buy_signal_probability > threshold:  # Buy BTC if past threshold
                                print(get_coinbase_price('BTC'))
                                buy_price = Decimal(str(get_coinbase_price('BTC')))

                                quote_size = profile.trade_quantity
                                tp_price = buy_price * Decimal(tp_sl_values['TP'])
                                sl_price = buy_price * Decimal(tp_sl_values['SL'])
                                product_id = "BTC-USDC"
                                # Create trade on Coinbase
                                success, order_id, client_order_id = create_trade_on_coinbase(coinbase_account,
                                                                                              product_id,
                                                                                              str(quote_size))
                                if success:
                                    fee_info, filled_size = fetch_order_summary(coinbase_account.access_token, order_id,
                                                                                client_order_id)
                                    # Log the trade in your Django app
                                    Trade.objects.create(
                                        profile=profile,
                                        coin_type='BTC',  # Assuming BTC trades for simplicity
                                        is_active=True,
                                        buy_price=float(buy_price),
                                        quantity_usdc=quote_size,
                                        quantity_coin=filled_size,
                                        stop_loss=sl_price,
                                        fee_amount=fee_info,
                                        take_profit=tp_price
                                    )

                        # If users only trade ETH
                        if profile.trade_btc == False and profile.trade_eth == True:
                            if eth_buy_signal_probability > threshold:  # Buy ETH if past threshold
                                print(get_coinbase_price('ETH'))
                                buy_price = Decimal(str(get_coinbase_price('ETH')))

                                quote_size = profile.trade_quantity
                                tp_price = buy_price * Decimal(tp_sl_values['TP'])
                                sl_price = buy_price * Decimal(tp_sl_values['SL'])
                                product_id = "ETH-USDC"
                                # Create trade on Coinbase
                                success, order_id, client_order_id = create_trade_on_coinbase(coinbase_account,
                                                                                              product_id,
                                                                                              str(quote_size))
                                if success:
                                    fee_info, filled_size = fetch_order_summary(coinbase_account.access_token, order_id,
                                                                                client_order_id)
                                    # Log the trade in your Django app
                                    Trade.objects.create(
                                        profile=profile,
                                        coin_type='ETH',  # Assuming ETH trades for simplicity
                                        is_active=True,
                                        buy_price=float(buy_price),
                                        quantity_usdc=quote_size,
                                        quantity_coin=filled_size,
                                        stop_loss=sl_price,
                                        fee_amount=fee_info,
                                        take_profit=tp_price
                                    )
