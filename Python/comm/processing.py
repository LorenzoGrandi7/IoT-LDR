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
from datetime import datetime
import logging
import sys
sys.path.append(r'C:\Users\loryg\OneDrive - Alma Mater Studiorum Università di Bologna\Università\Lezioni\IV Ciclo\IoT\Proj\src\Python')

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


def model_predict(ldr_sensor: LdrSensorManager, influxdb_cfg: dict[str, str]) -> None:
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
    try:
        # Initialize the DB client with the given configuration
        db_client = DBClient(influxdb_cfg['token'], influxdb_cfg['org'], influxdb_cfg['url'], influxdb_cfg['bucket'])

        # Load the past 24 hours of LDR sensor data from the database
        time_series_df = db_client.load_timeseries("24h", ldr_sensor.sensor_id)
        
        # Preprocess the time series data to remove outliers
        time_series_preprocess_df = preprocess_timeseries(time_series_df, 1.5)

        # Create and fit the Prophet model on the preprocessed data
        model = Prophet(interval_width=0.95, daily_seasonality=True, weekly_seasonality=False, yearly_seasonality=False)
        model.fit(time_series_preprocess_df)
        
        # Generate predictions for the next period based on the sensor's sampling period
        period = int(30 * 60 / ldr_sensor.cs_sampling_period)  # 30 minutes worth of future data
        future_points = model.make_future_dataframe(periods=period, freq=f'{ldr_sensor.cs_sampling_period}s')
        
        # Get the predicted values for the future points
        pred_df = model.predict(future_points)
        future_val = pred_df[pred_df['ds'] > datetime.now()]  # Filter future values after current time

        # Log the predictions for the sensor
        logger.info(f"Predictions LDR{ldr_sensor.sensor_id}: \n{future_val[['yhat']].head(2)}")
        
        # Store the predictions back in the database
        db_client.store_predictions(future_val, ldr_sensor.sensor_id)
    except Exception as e:
        logger.error(f"Exception: {e}")


def preprocess_timeseries(time_series_df: pd.DataFrame, std_threshold: float, window_size: str = "24h") -> pd.DataFrame:
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
    return time_series_processed_df
