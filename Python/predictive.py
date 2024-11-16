"""
Predictive Unit for IoT Sensor Data
Author: Lorenzo Grandi
License: Apache License, Version 2.0
"""

import asyncio
import json
import logging
from datetime import datetime
from time import sleep
import sys
import matplotlib.pyplot as plt

# Include the project source path for importing modules
sys.path.append(r'C:\Users\loryg\OneDrive - Alma Mater Studiorum Università di Bologna\Università\Lezioni\IV Ciclo\IoT\Proj\src\Python')

from comm import LdrSensorManager, model_predict
from sensorInfo import *

# ANSI color codes for terminal output
WHITE = "\033[0m"
RED = "\033[31m"
YELLOW = "\033[33m"
LIME = "\033[32m"
CYAN = "\033[36m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
BOLD = "\033[1m"

# Initialize logger for the predictive unit
logger = logging.getLogger('PREDICTIVE UNIT')
logger.setLevel(logging.INFO)

async def load_default_config() -> dict:
    """
    Load default configurations from the JSON file.
    
    Returns
    -------
    dict
        Dictionary containing the default configurations.
    """
    logger.debug("Loading default configurations")
    with open(r'.\default_config.json', 'r') as f:
        return json.load(f)
    
async def load_sensors_config() -> dict:
    """
    Load sensors configurations from the JSON file.
    
    Returns
    -------
    dict
        Dictionary containing the sensor configurations.
    """
    logger.debug("Loading sensors configurations")
    with open(r'.\sensors_config.json', 'r') as f:
        return json.load(f)
    
async def load_sensors():
    """
    Load configurations and initialize sensors.
    """
    logger.debug("Loading sensors")
    global ldr_sensors
    
    default_config = await load_default_config()
    sensors_config = await load_sensors_config()
    
    # Initialize sensors
    new_sensors = await setup_sensors(default_config, sensors_config)
    ldr_sensors = new_sensors
    
async def setup_sensors(default_config: dict, sensors_config: dict) -> list:
    """
    Set up LDR sensors based on configurations.

    Parameters
    ----------
    default_config : dict
        Default configurations.
    sensors_config : dict
        Sensor-specific configurations.

    Returns
    -------
    list
        List of initialized `LdrSensorManager` objects.
    """
    logger.debug("Setting up LDR sensors")
    
    mqtt_cfg = default_config['mqtt']
    influxdb_cfg = default_config['influxdb']
    coap_ip = default_config['coap']['ip']
    
    ldr_sensors = []
    for sensor_cfg in sensors_config['sensors']:
        # Extract configuration details
        sensor_id = sensor_cfg['id']
        coap_cfg = {"coap_ip": coap_ip, "coap_port": sensor_cfg["coap_port"]}
        position = Position(**sensor_cfg['position'])
        plant = Plant(**sensor_cfg['plant'])
        sampling_period = sensor_cfg['sampling_period']
        accum_window = sensor_cfg['accumulation_window']
        
        # Initialize sensor manager
        ldr_sensor = LdrSensorManager(coap_cfg, mqtt_cfg, influxdb_cfg, 
                                      sensor_id, position, plant, 
                                      sampling_period, accum_window)
        ldr_sensor.print_info()
        ldr_sensors.append(ldr_sensor)
    
    return ldr_sensors

async def reload_sensors():
    """
    Reload sensor configurations and update their instances.
    """
    logger.debug("Reloading sensors")
    global ldr_sensors
    
    try:
        # Load updated configurations
        default_config = await load_default_config()
        sensors_config = await load_sensors_config()
        
        for sensor_cfg in sensors_config['sensors']:
            sensor_id = sensor_cfg['id']
            existing_sensor = next((ldr for ldr in ldr_sensors if ldr.sensor_id == sensor_id), None)
            
            if existing_sensor:
                # Update the existing sensor
                existing_sensor.update_sensor(Position(**sensor_cfg['position']), 
                                              sensor_cfg['sampling_period'], 
                                              sensor_cfg['accumulation_window'], 
                                              Plant(**sensor_cfg['plant']))
                logger.debug(f"Updated sensor {sensor_id} with new config.")
                existing_sensor.print_info()
            else:
                # Add a new sensor if it doesn't exist
                coap_cfg = {"coap_ip": default_config['coap']['ip'], "coap_port": sensor_cfg["coap_port"]}
                mqtt_cfg = default_config['mqtt']
                influxdb_cfg = default_config['influxdb']
                
                new_sensor = LdrSensorManager(coap_cfg, mqtt_cfg, influxdb_cfg, 
                                              sensor_id, Position(**sensor_cfg['position']), 
                                              Plant(**sensor_cfg['plant']), 
                                              sensor_cfg['sampling_period'])
                ldr_sensors.append(new_sensor)
                logger.debug(f"Added new sensor {sensor_id}.")
    finally:
        logger.debug("Sensor configuration reloaded.")

def welcome_message() -> None:
    """
    Display a colorful welcome message for the predictive unit script.
    """
    welcome = (
        f"{WHITE}==================================================================={BLUE}\n"
        "\n"
        f"                   Welcome to {BOLD}{RED}P{YELLOW}r{LIME}e{CYAN}d{BLUE}i{MAGENTA}c{RED}t{YELLOW}i{LIME}v{CYAN}e{BLUE} U{MAGENTA}n{RED}i{YELLOW}t{WHITE}\n"
        "\n"
        f"{BLUE}This script provides predictive analysis of sensor data.{WHITE}\n"
        f"\n===================================================================\n"
    )
    print(f"{BLUE}{welcome}{WHITE}")

async def main():
    """
    Main function:
    - Periodically gathers recent sensor data (3 hours).
    - Predicts the next hour's data using a predefined model.
    - Reloads sensor configurations periodically.
    """
    global ldr_sensors

    # Load default configurations
    default_config = await load_default_config()
    influxdb_cfg = default_config['influxdb']
    
    # Initialize sensors
    await load_sensors()
    welcome_message()
    
    while True:
        # Pause for 30 seconds between cycles
        sleep(30)
        
        # Perform prediction for each sensor
        for ldr_sensor in ldr_sensors:
            model_predict(ldr_sensor, influxdb_cfg)
        
        # Reload sensor configurations to reflect updates
        await reload_sensors()

if __name__ == "__main__":
    asyncio.run(main())
