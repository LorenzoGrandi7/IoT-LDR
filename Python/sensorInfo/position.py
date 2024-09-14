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
from dataclasses import dataclass, field

@dataclass
class Position():
    """Sensor position manager."""
    position_id: str
    name: str
    description: str
    sensor_id: str = ""
    logger: logging.Logger = field(init=False, default=logging.getLogger('Position'))
    
    def __post_init__(self):
        self.logger.setLevel(logging.INFO)
        
    def update(self, position_id: str = None, name: str = None, description: str = None, sensor_id: str = None) -> None:
        """
        Update the position settings
        
        Parameters
        ---------
        **position_id** : str
            New position ID
        **name** : int
            New name for the position
        **description** : str
            New description for the position
        **sensor_id** : str
            New sensor ID for the position
        """
        if position_id:
            self.position_id = position_id
        if name:
            self.name = name
        if description:
            self.description = description
        if sensor_id:
            self.sensor_id = sensor_id
        
    def print_position(self):
        self.logger.info(f"position:{self.position_id}:{self.name}")