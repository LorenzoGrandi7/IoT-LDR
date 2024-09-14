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

import datetime
import logging
import numpy as np
import aiocoap
import aiocoap.resource as resource
from aiocoap import Message
import asyncio

from sensorInfo.plant import Plant
from sensorInfo.position import Position
from comm.mqtt_client import MqttClient
from comm.db_client import DBClient

class LdrSensorManager(resource.Resource):
    """LDR sensor manager, includes MQTT protocol for sending configuration and InfluxDB for storing time-series."""
    def __init__(self, coap_cfg: dict[str, None], mqtt_cfg: dict[str, None], influxdb_cfg: dict[str, str],
                 sensor_id: str, position: Position, plant: Plant, sampling_period: int, accum_window_len: int) -> None:
        super().__init__()
        self.logger = logging.getLogger("CoAP")
        self.logger.setLevel(logging.INFO)
        self.LDR_start_timeseries = datetime.datetime.now()
        """Starting timeseries timestamp."""
        
        self.coap_cfg = coap_cfg
        """Sensor CoAP settings."""
        self.mqtt_client = MqttClient(mqtt_cfg['ip'], mqtt_cfg['port'], mqtt_cfg['user'], mqtt_cfg['password'],
                                      sensor_id, position, sampling_period)
        """Sensor MQTT client."""
        self.influxdb_client = DBClient(influxdb_cfg['token'], influxdb_cfg['org'], influxdb_cfg['url'], influxdb_cfg['bucket'])
        """Sensor InfluxDB client."""
        self.sensor_id = sensor_id
        """Sensor ID."""
        self.plant = plant
        self.plant.sensor_id = sensor_id
        """Sensor associated plant."""
        self.position  = position
        self.position.sensor_id = sensor_id
        """"Plant current position."""
        self.cs_sampling_period = sampling_period
        """Sensor current CoAP sampling period [s]."""
        self.ns_sampling_period = sampling_period
        """New LDR CoAP sampling period [s]."""
        
        self.last_time       = 0
        """Sensor last message timestamp."""
        self.receive_latency = 0
        """Sensor last message latency."""
        self.latency_list    = np.array([], dtype=float)
        """Sensor latency accumulator."""
        self.accum_window_len    = accum_window_len * 60 / sampling_period
        """Time period [m] for latency mean computation."""
        self.coap_ldr_value = 0
        """Value read from LDR sensors."""    
        
        self.N_predictions = influxdb_cfg['N_hours'] * 60 * 60 / sampling_period
        """Time period [h] for LDR value prediction."""
        self.ldr_timeseries = np.array([], dtype=int)
        """LDR time-series."""
        
    def print_info(self) -> None:
        """Print sensor info"""
        self.logger.debug(f"ID: {self.sensor_id}, position: {self.position.name}, sampling period: {self.cs_sampling_period}")
        
        
    async def render_put(self, request) -> Message:
        """
        Define the ``render_put`` function, which must be implemented as extension of Resource for CoAP communication.
        
        Parameters
        ----------
        **request** : Any
            The CoAP message request.
        
        Returns
        -------
        **message** : Message
            CoAP message found when LDR value sensed changes.
        """
        
        decoded_string = request.payload.decode('utf-8')
        query_params = dict(param.split('=') for param in decoded_string.split('&'))
        
        sensor_id = query_params.get('sensor_id')
        location = query_params.get('location')
        data = int(query_params.get('data'))
        self.logger.info(f"CoAP message received: ID({sensor_id}) - position({location}) - value({data}%)")
        
        self.store_value(query_params)
        message = Message(code=aiocoap.CHANGED, payload=request.payload)
        return message
    
    async def coap_server(self) -> None:
        """
        CoAP server for sensor.
        """
        root = resource.Site()
        root.add_resource([".well-known", "core"], resource.WKCResource(root.get_resources_as_linkheader))
        root.add_resource([f"ldrData{self.sensor_id}"], self)

        # Create CoAP server context for sensor
        await aiocoap.Context.create_server_context(root, bind=(self.coap_cfg['coap_ip'], self.coap_cfg['coap_port']))
        await asyncio.get_running_loop().create_future()
        
    def update_sensor(self, position: Position, sampling_period: int, accum_window_len: int, plant: Plant) -> None:
        """
        Update the sensor config
        
        Parameters
        ----------
        **position**: Position
            New sensor position.
        **sampling_period**: int
            New sampling period.
        **accum_window_len**: int
            New accumulation window.
        **plant**: Plant
            New plant info.
        """
        self.position = position
        self.ns_sampling_period = sampling_period
        self.plant = plant
        self.ns_sampling_period = sampling_period
        self.accum_window_len    = accum_window_len * 60 / sampling_period
        
        self.mqtt_client.update_sensor(position, sampling_period)

    def store_value(self, content : dict[str, str]) -> None:
        """
        Gets the timestamp when the request is received and store the LDR value sensed.
        
        Parameters
        ----------
        **content** : dict[str, str]
            The parameters out from the CoAP message.
        """
        self.store_timestamp(datetime.datetime.now().timestamp())
        self.coap_ldr_value = content.get('data')
        self.influxdb_client.store_value("ldrValue", "ldr", self.sensor_id, self.coap_ldr_value)
    
    def store_timestamp(self, receive_time: float) -> None:
        """
        Store the current receive timestamp, managing the sampling period setting changes.
        
        Parameters
        ----------
        **receive_time** : float
            Timestamp of the last CoAP message.
        """
        if self.ns_sampling_period != self.cs_sampling_period:
            # If the sampling period is changed in the configuration file, the latency list is cleared
            self.logger.info("Flushing the latency accumulator.")
            self.latency_list = np.array([], dtype=float)
            self.cs_sampling_period = self.ns_sampling_period
        elif self.last_time:
            self.receive_latency = receive_time - self.last_time - self.cs_sampling_period
            
        self.last_time = receive_time
        self.latency_list = np.append(self.latency_list, self.receive_latency)
        
        if len(self.latency_list) == int(self.accum_window_len):
            latency_mean = self.compute_latency_mean(self.latency_list, int(self.accum_window_len))
            self.influxdb_client.store_value("meanLat", "mean_lat", self.sensor_id, latency_mean)
            
            
    def compute_latency_mean(self, latency_list: np.ndarray, window_size: int) -> float:
        """Compute latency mean.
        
        Parameters
        ---------
        **latency_list**: list
            List of the latencies of each CoAP message received.
        **window_size**: int
            Number of elements of the list.
            
        Returns
        ------
        **latency_mean**: float
            The mean latency of the latency list.
        """
        latency_mean = np.mean(self.latency_list) * 1e6
        self.latency_list = np.array([], dtype=float)
        logging.info(f"Mean latency sensor {self.sensor_id}: {latency_mean: .2f}us")
        self.influxdb_client.store_mean_lat_influxdb(latency_mean, self.sensor_id)
        return latency_mean
        
    
    def compute_hour_ldr_mean(self, ldr_timeseries: np.ndarray):
        hour_ldr_timeseries = self.influxdb_client.load_timeseries(1, self.sensor_id)   # the last hour sensed values are load to process a mean
        hour_ldr_mean = np.mean(hour_ldr_timeseries)
        self.influxdb_client.store_ldr_influxdb