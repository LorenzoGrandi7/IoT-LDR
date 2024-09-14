import logging
import time
import asyncio
from datetime import datetime
import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

class DBClient():
    """InfluxDB client manager."""    
    def __init__(self, db_token: str, db_org: str, db_url: str, db_bucket: str):
        self.logger = logging.getLogger("InfluxDB")
        self.logger.setLevel(logging.INFO)
        
        self.db_cfg = {
            "token"  : db_token,
            "org"    : db_org,
            "url"    : db_url,
            "bucket" : db_bucket
        }
        
    def store_value(self, measurement: str, field: str, sensor_id: str, value: int) -> None:
        """
        Store the measurement value on a remote InfluxDB database.
        
        Parameters
        ----------
        **value** : int
            Value to be stored.
        **measurement**: str
            Measurement in which `value` is stored.
        **sensor_id**: str
            Sensor ID.
        """
        self.logger.debug(f"Storing value from {sensor_id} in {measurement}: {value}")
        client = InfluxDBClient(url=self.db_cfg['url'], token=self.db_cfg['token'], org=self.db_cfg['org'])
        write_api = client.write_api(write_options=SYNCHRONOUS)
        
        p = Point(measurement).tag("sensor", sensor_id).field(field, int(value)).time(datetime.now(), WritePrecision.NS)
        write_api.write(bucket=self.db_cfg['bucket'],org=self.db_cfg['org'],record=p)
        
        client.close()
        
        
    # def store_ldr_influxdb(self, ldr_value: int, sensor_id: str) -> None:
    #     """
    #     Store the LDR value on a remote InfluxDB database.
        
    #     Parameters
    #     ----------
    #     **ldr_value** : int
    #         Sensed light to be stored.
    #     **sensor_id**: str
    #         Sensor ID
    #     """
    #     self.logger.debug(f"Storing values sensed from LDR{sensor_id}: {ldr_value}")
    #     client = InfluxDBClient(url=self.db_cfg['url'], token=self.db_cfg['token'], org=self.db_cfg['org'])
    #     write_api = client.write_api(write_options=SYNCHRONOUS)
        
    #     p = Point("ldrValue").tag("sensor", sensor_id).field("ldr", int(ldr_value)).time(datetime.utcnow(), WritePrecision.NS)
    #     write_api.write(bucket=self.db_cfg['bucket'],org=self.db_cfg['org'],record=p)
        
    #     client.close()
        
    # def store_mean_lat_influxdb(self, mean_lat: float, sensor_id: str) -> None:
    #     """
    #     Store the LDR values on a remote InfluxDB database.
        
    #     Parameters
    #     ----------
    #     **mean_lat** : float
    #         Mean latency computed.
    #     **sensor_id**: str
    #         Sensor ID
    #     """
    #     self.logger.debug(f"Storing values sensed from LDR{sensor_id}: {mean_lat}")
    #     client = InfluxDBClient(url=self.db_cfg['url'], token=self.db_cfg['token'], org=self.db_cfg['org'])
    #     write_api = client.write_api(write_options=SYNCHRONOUS)
        
    #     p = Point("meanLat").tag("sensor", sensor_id).field("mean_lat", int(round(mean_lat, 0))).time(datetime.utcnow(), WritePrecision.NS)
    #     write_api.write(bucket=self.db_cfg['bucket'],org=self.db_cfg['org'],record=p)
        
    #     client.close()
        
    async def load_timeseries(self, N_hours: int, sensor_id: str) -> np.ndarray:
        """Load a timeseries of the last `N_hours` hours any `N_hours`."""
        client = InfluxDBClient(url=self.db_cfg['url'], token=self.db_cfg['token'], org=self.db_cfg['org'])
        query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: -{N_hours}h, v.timeRangeStop)
                |> filter(fn: (r) => r._measurement == "ldr")
                |> filter(fn: (r) => r.sensor == "{sensor_id}")
            '''
        
        while True:
            start_time = time.time()
            await asyncio.sleep(N_hours * 60)
            elapsed_time = time.time() - start_time
            if elapsed_time >= N_hours * 60:
                query_api = client.query_api()
                result = query_api.query(query)
                
                data = np.array([], dtype=int)
                for table in result:
                    for record in table.records:
                        np.append(data, record)
                        
                return data
    
    def predictor(self, time_series: np.ndarray, sampling_period: int, N: int, order=(5,1,0)) -> np.array:
        """
        Predict future values of a time series using an ARIMA model.
        
        Parameters
        ----------
        **time_series** : np.array
            The historical data from which the prediction is made.
        **sampling_period** : int
            The sampling period in seconds (e.g., 60 for 1 minute, 3600 for 1 hour).
        **N** : int
            The number of hours into the future to predict.
        **order** : tuple
            The (p, d, q) order of the ARIMA model. Default is (5, 1, 0).
        
        Returns
        -------
        **np.array**
            The predicted values for the next N hours.
        """
        num_samples = int(N * 3600 * sampling_period)
        series = pd.Series(time_series)
        model = ARIMA(series, order=order)
        model_fit = model.fit()
        
        forecast = model_fit.forecast(steps=num_samples)
        return forecast.to_numpy()