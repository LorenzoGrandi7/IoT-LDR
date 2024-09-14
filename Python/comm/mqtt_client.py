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

import logging
import asyncio
import paho.mqtt.client as mqtt

from sensorInfo import Position

class MqttClient():
    """MQTT client manager."""
    def __init__(self, mqtt_ip: str, mqtt_port: int, mqtt_user: str, mqtt_password: str,
                 sensor_id: str, position: Position, sampling_period: int):
        self.logger = logging.getLogger("MQTT")
        self.logger.setLevel(logging.INFO)
        
        self.mqtt_cfg = {
            "ip"         : mqtt_ip,
            "port"       : mqtt_port,
            "keep_alive" : 60,
            "username"   : mqtt_user,
            "password"   : mqtt_password
        }
        """MQTT configuration for the node."""
        
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.username_pw_set(self.mqtt_cfg['username'], self.mqtt_cfg['password'])
        
        self.sensor_id = sensor_id
        self.position = position
        self.sampling_period = sampling_period
    
    def update_sensor(self, position: Position, sampling_period: int):
        """Update the sensor config"""
        self.position = position
        self.sampling_period = sampling_period
    
    def on_connect(self, client, userdata, flags, rc) -> None:
        """
        Define the on_connect callback.
        
        Parameters
        ----------
        **rc**: int
            MQTT response code.
        """
        self.logger.info(f"Connected to MQTT broker, rc={rc}")
    
    def mqtt_connect(self) -> None:
        """MQTT connect routine."""
        self.client.connect(self.mqtt_cfg['ip'], self.mqtt_cfg['port'], self.mqtt_cfg['keep_alive'])
        self.client.loop_start()

    def mqtt_disconnect(self) -> None:
        """MQTT disconnect routine."""
        self.client.loop_stop()
        self.client.disconnect()

    def mqtt_publish(self, topic: str, payload: None, qos: int =2) -> None:
        """
        MQTT publish routine
        
        Parameters
        ----------
        **topic** : str
            The topic that the message should be published on.
        **payload** : None
            The actual message to send. If not given, or set to None a zero length message will be used. 
            Passing an int or float will result in the payload being converted to a string representing that number. 
            If you wish to send a true int/float, use struct.pack() to create the payload you require.
        **qos** : int
            The quality of service level to use.
        """
        self.logger.debug(f"Publishing to topic '{topic}' with payload '{payload}' and QoS {qos}")
        self.client.publish(topic, payload, qos=qos)

    async def periodic_publish(self) -> None:
        """
        MQTT periodic (10s) publish routine.
        
        Parameters
        ----------
        **sensor_id**: str
            Sensor ID to be published.
        **sampling_period**: int
            Sampling period to be published.
        **position**: Position
            Position to be published.
        """
        self.mqtt_connect()
        try:
            while True:
                self.mqtt_publish(f"home/ldr{self.sensor_id}/sampling_period", self.sampling_period)
                self.mqtt_publish(f"home/ldr{self.sensor_id}/position", self.position.name)
                await asyncio.sleep(5)
        finally:
            self.mqtt_disconnect()
