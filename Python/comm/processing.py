"""
Copyright 2024 Lorenzo Grandi

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from prophet import Prophet
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dateutil.easter import easter
import logging
import sys
sys.path.append(r'C:\Users\loryg\OneDrive\Desktop\IoT\IoT-LDR\Python')
from sklearn.preprocessing import StandardScaler

from comm import LdrSensorManager
from comm import DBClient
from tools import *

# Set up logger for processing unit
logger = logging.getLogger("processing unit")
logger.setLevel(logging.INFO)

# Custom logging filter to hide certain logs from the cmdstanpy module
class CmdStanpyFilter(logging.Filter):
    def filter(self, record):
        return not record.getMessage().startswith("")

logging.getLogger("cmdstanpy").addFilter(CmdStanpyFilter())

from datetime import datetime, timedelta
from dateutil.easter import easter

def generate_holidays(start_year: int, end_year: int) -> pd.DataFrame:
    """
    Generates a DataFrame of weekends and public holidays in Italy between the specified years.
    """
    # Generate a list of dates for weekends
    weekends = []
    for year in range(start_year, end_year + 1):
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31)
        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() in [5, 6]:  # Saturday (5) and Sunday (6)
                weekends.append(current_date)  # Ensure datetime.datetime type
            current_date += timedelta(days=1)

    # Define fixed-date holidays in Italy
    fixed_holidays = [
        "01-01",  # New Year's Day
        "01-06",  # Epiphany
        "04-25",  # Liberation Day
        "05-01",  # International Workers' Day
        "06-02",  # Republic Day
        "08-15",  # Assumption Day
        "11-01",  # All Saints' Day
        "12-08",  # Immaculate Conception
        "12-25",  # Christmas Day
        "12-26",  # St. Stephen's Day
    ]

    holidays = []
    for year in range(start_year, end_year + 1):
        # Add fixed-date holidays
        for holiday in fixed_holidays:
            holiday_date = datetime.strptime(f"{year}-{holiday}", "%Y-%m-%d")
            holidays.append(holiday_date)
        
        # Add Easter Monday (Pasquetta)
        easter_monday = easter(year) + timedelta(days=1)
        holidays.append(datetime(easter_monday.year, easter_monday.month, easter_monday.day))  # Ensure datetime.datetime type

    # Combine weekends and holidays, removing duplicates
    all_holidays = list(set(weekends + holidays))
    all_holidays.sort()

    # Create a DataFrame with holidays
    holidays_df = pd.DataFrame({
        'holiday': 'italian_holiday',
        'ds': all_holidays
    })

    return holidays_df

    


def model_predict(ldr_sensor: LdrSensorManager, influxdb_cfg: dict[str, str], holidays: pd.DataFrame) -> None:
    """
    Uses the Prophet model to predict future LDR sensor readings based on the past 24 hours of data.
    
    This function connects to a database to retrieve the LDR sensor's time-series data, 
    preprocesses it, and then uses Prophet to forecast future readings based on that data.
    The predictions are then stored back into the database.

    Parameters
    ----------
    ldr_sensor : LdrSensorManager
        The LDR sensor object that holds sensor information such as the sensor ID and sampling period.
        
    influxdb_cfg : dict[str, str]
        A dictionary containing the configuration for connecting to the InfluxDB instance.
        Expected keys: 'token', 'org', 'url', 'bucket'.
    
    Returns
    ------
    None
        This function does not return anything. The predictions are stored in the database.
    
    Raises
    ------
    Exception
        If any error occurs during the prediction process, it will be caught and logged.
    """
    scaler = StandardScaler()

    # Initialize the DB client with the given configuration
    db_client = DBClient(influxdb_cfg['token'], influxdb_cfg['org'], influxdb_cfg['url'], influxdb_cfg['bucket'])

    # Load the past 24 hours of LDR sensor data from the database
    time_series_df = db_client.load_timeseries("inf", ldr_sensor.sensor_id)
    
    # Preprocess the time series data to remove outliers
    time_series_preprocess_df = preprocess_timeseries(time_series_df, 1)
    y_values = time_series_preprocess_df['y'].values.reshape(-1, 1)
    time_series_preprocess_df['y'] = scaler.fit_transform(y_values)

    start_training = datetime.now()
    # Create and fit the Prophet model on the preprocessed data
    model = Prophet(interval_width=0.95, daily_seasonality=True, weekly_seasonality=False, yearly_seasonality=False, holidays=holidays)
    model.fit(time_series_preprocess_df)
    
    # Generate predictions for the next period based on the sensor's sampling period
    # period = int(120 * 60 / ldr_sensor.cs_sampling_period)  # 30 minutes worth of future data
    # future_points = model.make_future_dataframe(periods=period, freq=f'{ldr_sensor.cs_sampling_period}s')
    future_points = model.make_future_dataframe(periods=4, freq=f'{influxdb_cfg['prediction_period_min']}min')
    
    # Get the predicted values for the future points
    pred_df = model.predict(future_points)
    pred_df['yhat'] = scaler.inverse_transform(pred_df[['yhat']])
    pred_df['yhat_lower'] = scaler.inverse_transform(pred_df[['yhat_lower']])
    pred_df['yhat_upper'] = scaler.inverse_transform(pred_df[['yhat_upper']])
    future_val = pred_df[pred_df['ds'] >= datetime.now()]  # Filter future values after current time
    logger.debug(f"Predicted {future_val['yhat'].shape[0]} future points")

    # Log the predictions for the sensor
    logger.debug(f"Predicted: lower({future_val['yhat_lower'].values[0]:.2f}), pred({future_val['yhat'].values[0]:.2f}), upper({future_val['yhat_upper'].values[0]:.2f})")
    list(map(lambda x: logger.debug(f"{x: .2f}"), future_val['yhat'].values))
    list(map(lambda x: logger.debug(f"{x}"), future_val['ds'].values))
    # Store the predictions back in the database
    db_client.store_predictions(future_val, ldr_sensor.sensor_id)
    db_client.store_predictions_lower(future_val, ldr_sensor.sensor_id)
    db_client.store_predictions_upper(future_val, ldr_sensor.sensor_id)


def preprocess_timeseries(time_series_df: pd.DataFrame, std_threshold: float, window_size: str = "1h") -> pd.DataFrame:
    """
    Preprocesses the LDR sensor time-series data by removing outliers based on a standard deviation threshold.
    
    The function calculates the rolling mean and standard deviation for the time series using the specified
    window size, and removes data points that deviate from the mean by more than a specified threshold of the 
    standard deviation. The processed time series is returned as a cleaned DataFrame.

    Parameters
    ----------
    time_series_df : pd.DataFrame
        The raw time series data for the LDR sensor, which must have columns 'ds' (datetime) and 'y' (sensor readings).
        
    std_threshold : float
        The number of standard deviations used to identify outliers. Data points whose absolute deviation 
        from the rolling mean exceeds this threshold will be removed.
        
    window_size : str, optional, default: "24h"
        The size of the rolling window used to calculate the mean and standard deviation (e.g., "24h", "1h", "10min").
    
    Returns
    ------
    pd.DataFrame
        The cleaned time series DataFrame with outliers removed.
    
    Notes
    ------
    This function uses the rolling mean and standard deviation to identify and remove outliers.
    The function assumes that the 'ds' column contains datetime values and the 'y' column contains the sensor data.
    """
    # Make a copy of the time series data to avoid modifying the original data
    time_series_copy_df = time_series_df.copy()
    
    # Set the 'ds' column as the index
    time_series_copy_df.set_index('ds', inplace=True)
    
    # Calculate rolling mean and standard deviation over the specified window size
    rolling_window = time_series_copy_df.rolling(window_size)
    mean_series = rolling_window.mean()
    std_series = rolling_window.std()
    
    # List of indices to be removed (outliers)
    remove_idx = []
    
    # Check each data point for being an outlier
    for idx, val in time_series_copy_df['y'].items():
        mean = mean_series.get(idx, None)
        std = std_series.get(idx, None)
        
        # If the mean or std is not available for a point, skip it
        if mean is None or std is None:
            continue

        # Calculate the threshold for outlier detection
        threshold = std_threshold * std
        if abs(val - mean) > threshold:
            remove_idx.append(idx)
    
    # Drop the outliers from the time series data
    time_series_processed_df = time_series_copy_df.drop(remove_idx)
    
    # Reset index and return the cleaned DataFrame
    time_series_copy_df.reset_index(inplace=True)
    time_series_processed_df.reset_index(inplace=True)

    time_series_processed_df['y'] = pd.to_numeric(time_series_processed_df['y'], errors='coerce')
    time_series_processed_df.dropna(subset=['y'], inplace=True)

    return time_series_processed_df

