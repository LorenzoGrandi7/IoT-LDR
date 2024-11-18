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
import sys
sys.path.append(r'C:\Users\loryg\OneDrive\Desktop\IoT\IoT-LDR\Python')

from sensorInfo.plant import Plant
from sensorInfo.position import Position
from comm.mqtt_client import MqttClient
from comm.db_client import DBClient

class LdrSensorManager(resource.Resource):
    """
    A manager class for Light-Dependent Resistor (LDR) sensors. Handles CoAP communication,
    MQTT configuration updates, and InfluxDB storage for time-series data and performance metrics.
    
    Attributes
    ----------
    coap_cfg : dict[str, None]
        Configuration for the CoAP communication protocol (e.g., IP, port).
    mqtt_client : MqttClient
        MQTT client for publishing sensor updates.
    influxdb_client : DBClient
        InfluxDB client for storing time-series data and metrics.
    sensor_id : str
        Unique identifier for the sensor.
    plant : Plant
        Information about the plant associated with the sensor.
    position : Position
        Geographic or logical position of the sensor.
    cs_sampling_period : int
        Current sampling period for CoAP communication (in seconds).
    ns_sampling_period : int
        Updated sampling period, applied dynamically if changed.
    accum_window_len : int
        Number of messages used to compute the latency mean.
    latency_list : np.array
        Array to store latency values for analysis.
    ldr_timeseries : np.array
        Stores the time-series data for LDR values.
    coap_ldr_value : int
        Latest LDR value received via CoAP communication.
    last_time : float
        Timestamp of the last received CoAP message.
    receive_latency : float
        Latency between expected and actual receipt of a CoAP message.
    """

    def __init__(self, coap_cfg: dict[str, None], mqtt_cfg: dict[str, None], influxdb_cfg: dict[str, str],
                 sensor_id: str, position: Position, plant: Plant, sampling_period: int, accum_window_len: int) -> None:
        """
        Initializes the LDR Sensor Manager.

        Parameters
        ----------
        coap_cfg : dict[str, None]
            CoAP protocol configuration dictionary.
        mqtt_cfg : dict[str, None]
            MQTT broker configuration dictionary.
        influxdb_cfg : dict[str, str]
            InfluxDB connection configuration dictionary.
        sensor_id : str
            Unique ID for the sensor.
        position : Position
            Sensor's position (e.g., location or identifier).
        plant : Plant
            Information about the associated plant.
        sampling_period : int
            Sampling period in seconds for CoAP communication.
        accum_window_len : int
            Duration (in minutes) for computing latency mean.
        """
        super().__init__()
        self.logger = logging.getLogger("CoAP")
        self.logger.setLevel(logging.INFO)

        self.LDR_start_timeseries = datetime.datetime.now()
        self.coap_cfg = coap_cfg
        self.mqtt_client = MqttClient(mqtt_cfg['ip'], mqtt_cfg['port'], mqtt_cfg['user'], mqtt_cfg['password'],
                                      sensor_id, position, sampling_period)
        self.influxdb_client = DBClient(influxdb_cfg['token'], influxdb_cfg['org'], influxdb_cfg['url'], influxdb_cfg['bucket'])
        self.sensor_id = sensor_id
        self.plant = plant
        self.plant.sensor_id = sensor_id
        self.position = position
        self.position.sensor_id = sensor_id
        self.cs_sampling_period = sampling_period
        self.ns_sampling_period = sampling_period
        self.last_time = 0
        self.receive_latency = 0
        self.latency_list = np.array([], dtype=float)
        self.accum_window_len = accum_window_len * 60 / sampling_period
        self.coap_ldr_value = 0
        self.ldr_timeseries = np.array([], dtype=int)

    def print_info(self) -> None:
        """
        Prints basic information about the sensor configuration.
        """
        self.logger.debug(f"ID: {self.sensor_id}, position: {self.position.name}, sampling period: {self.cs_sampling_period}")

    async def render_put(self, request) -> Message:
        """
        Handles CoAP PUT requests for receiving LDR data updates.

        Parameters
        ----------
        request : Message
            Incoming CoAP request.

        Returns
        -------
        Message
            Response indicating the request was successfully processed.
        """
        decoded_string = request.payload.decode('utf-8')
        query_params = dict(param.split('=') for param in decoded_string.split('&'))

        sensor_id = query_params.get('sensor_id')
        location = query_params.get('location')
        data = query_params.get('data')
        self.logger.info(f"CoAP message received: ID({sensor_id}) - position({location}) - value({data}%)")

        self.store_value(query_params)
        message = Message(code=aiocoap.CHANGED, payload=request.payload)
        return message

    async def coap_server(self) -> None:
        """
        Starts the CoAP server for handling sensor requests.
        """
        root = resource.Site()
        root.add_resource([".well-known", "core"], resource.WKCResource(root.get_resources_as_linkheader))
        root.add_resource([f"ldrData{self.sensor_id}"], self)

        await aiocoap.Context.create_server_context(root, bind=(self.coap_cfg['coap_ip'], self.coap_cfg['coap_port']))
        await asyncio.get_running_loop().create_future()

    def update_sensor(self, position: Position, sampling_period: int, accum_window_len: int, plant: Plant) -> None:
        """
        Updates the sensor configuration dynamically.

        Parameters
        ----------
        position : Position
            New sensor position.
        sampling_period : int
            New sampling period in seconds.
        accum_window_len : int
            New accumulation window length in minutes.
        plant : Plant
            Updated plant information.
        """
        self.position = position
        self.ns_sampling_period = sampling_period
        self.plant = plant
        self.accum_window_len = accum_window_len * 60 / sampling_period

        self.mqtt_client.update_sensor(position, sampling_period)

    def store_value(self, content: dict[str, str]) -> None:
        """
        Stores the received LDR sensor value and timestamp in the database.

        Parameters
        ----------
        content : dict[str, str]
            Dictionary containing CoAP message parameters.
        """
        self.store_timestamp(datetime.datetime.now().timestamp())
        self.coap_ldr_value = content.get('data')
        self.influxdb_client.store_value("ldrValue", "ldr", self.sensor_id, self.coap_ldr_value)

    def store_timestamp(self, receive_time: float) -> None:
        """
        Stores the timestamp of the received CoAP message, handling sampling period changes.

        Parameters
        ----------
        receive_time : float
            Timestamp of the CoAP message receipt.
        """
        if self.ns_sampling_period != self.cs_sampling_period:
            self.logger.info("Flushing the latency accumulator.")
            self.latency_list = np.array([], dtype=float)
            self.cs_sampling_period = self.ns_sampling_period
        elif self.last_time:
            self.receive_latency = receive_time - self.last_time - self.cs_sampling_period

        self.last_time = receive_time
        self.latency_list = np.append(self.latency_list, self.receive_latency)

        if len(self.latency_list) == int(self.accum_window_len):
            latency_mean = self.compute_latency_mean()
            self.influxdb_client.store_mean_lat_influxdb(latency_mean, self.sensor_id)

    def compute_latency_mean(self) -> float:
        """
        Computes the mean latency for the accumulated CoAP messages.

        Returns
        -------
        float
            The mean latency in microseconds.
        """
        latency_mean = np.mean(self.latency_list) * 1e6
        self.latency_list = np.array([], dtype=float)
        self.logger.info(f"Mean latency sensor {self.sensor_id}: {latency_mean:.2f}us")
        self.influxdb_client.store_mean_lat_influxdb(latency_mean, self.sensor_id)
        return latency_mean
