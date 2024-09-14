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

from dataclasses import dataclass

@dataclass
class Plant():
    """Plant dataclass"""
    type: str
    """Type of the plant"""
    light_amount: int
    """Number of ours the plant needs exposure to sunlight"""
    sensor_id: str
    """Associated sensor ID"""
        
    def update_plant(self, type: str = None, light_amount: int = None, sensor_id: str = None) -> None:
        """
        Update the plant settings
        
        Parameters
        ----------
        **type** : str
            New name of the plant
        **light_amount** : int
            New light amount of the plant
        **sensor_id** : str
            New sensor ID for the plant
        """
        if type:
            self.name = type
        if light_amount:
            self.light_amount = light_amount
        if sensor_id:
            self.sensor_id = sensor_id