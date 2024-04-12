import numpy as np
import pandas as pd
import requests
import ccxt
from datetime import datetime
import os
import sys
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from keras.models import load_model
from joblib import load
import pandas_ta as ta


def get_buy_signal_probability():
    def fetch_recent_data(symbol, number_of_candles=165, timeframe='30m'):
        exchange = ccxt.binance()
        milliseconds_per_candle = 1800000  # 30 minutes
        since = exchange.milliseconds() - milliseconds_per_candle * number_of_candles
        candles = exchange.fetch_ohlcv(symbol, timeframe, since, number_of_candles)
        df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df

    def get_fear_and_greed_index():
        response = requests.get("https://api.alternative.me/fng/")
        data = response.json()
        return data['data'][0]['value']

    def get_bitcoin_dominance():
        response = requests.get("https://api.coingecko.com/api/v3/global")
        data = response.json()
        return data['data']['market_cap_percentage']['btc'] / 100

    def calculate_indicators(df):
        df['SMA'] = ta.sma(df['close'], length=150)
        df['RSI'] = ta.rsi(df['close'], length=14)
        df['OBV'] = ta.obv(df['close'], df['volume'])
        df['ATR'] = ta.atr(df['high'], df['low'], df['close'])
        return df

    def calculate_all_signals(df, ma_backcandles, obv_backcandles, obv_threshold, atr_backcandles, atr_threshold):
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
    xgboost_model = load('./binary_btc_xgboost_model_10k.joblib')
    lstm_model = load_model('./new_binary_btc_LSTM_model_10k.keras')
    meta_model = load('./meta_learner_10k.joblib')

    # Candles
    backcandles = 15
    obv_backcandles = 150
    obv_threshold = 0.015
    atr_backcandles = backcandles
    atr_threshold = 0.05

    # Fetch live data
    btc_data = fetch_recent_data('BTC/USDT')
    btc_data = calculate_indicators(btc_data)
    df = calculate_all_signals(btc_data, backcandles, obv_backcandles, obv_threshold, atr_backcandles, atr_threshold)

    fear_and_greed_index = get_fear_and_greed_index()
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
    scaler_xgb = load('./xgboost_scaler.joblib')
    scaler_lstm = load('./new_minmax_lstm_scaler.joblib')
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


if __name__ == "__main__":
    probability = get_buy_signal_probability()
    print(probability)
