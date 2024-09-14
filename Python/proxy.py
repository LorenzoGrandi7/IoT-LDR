import asyncio
import json
import logging
from watchdog.observers import Observer

from comm import *
from tools import *
from sensorInfo import *

logger = logging.getLogger("MAIN")
logger.setLevel(logging.INFO)

WHITE = "\033[0m"
BLACK = "\033[30m"
RED = "\033[31m"
LIME = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
LIGHT_GRAY = "\033[37m"
BOLD = "\033[1m"
ITALIC = "\033[3m"

async def load_default_config() -> dict:
    """Load default configurations from the JSON file."""
    logger.debug("Loading default configurations")
    with open('default_config.json', 'r') as f:
        return json.load(f)

async def load_sensors_config() -> dict:
    """Load sensors configuration from the JSON file."""
    logger.debug("Loading sensors configurations")
    with open('sensors_config.json', 'r') as f:
        return json.load(f)

async def setup_sensors(default_config: dict, sensors_config: dict) -> list:
    """Setup LDR sensors based on the configuration."""
    logger.debug("Setup LDR sensors")
    mqtt_cfg = default_config['mqtt']
    influxdb_cfg = default_config['influxdb']
    coap_ip = default_config['coap']['ip']
    
    ldr_sensors = []
    for sensor_cfg in sensors_config['sensors']:
        sensor_id = sensor_cfg['id']
        coap_cfg = {"coap_ip": coap_ip, "coap_port": sensor_cfg["coap_port"]}
        position = Position(**sensor_cfg['position'])
        plant = Plant(**sensor_cfg['plant'])
        sampling_period = sensor_cfg['sampling_period']
        accum_window = sensor_cfg['accumulation_window']
    
        ldr_sensor = LdrSensorManager(coap_cfg, 
                                      mqtt_cfg, 
                                      influxdb_cfg, 
                                      sensor_id, 
                                      position, 
                                      plant, 
                                      sampling_period, 
                                      accum_window)
        ldr_sensor.print_info()
        ldr_sensors.append(ldr_sensor)
    
    return ldr_sensors

async def load_sensors():
    """Load configuration and create sensors."""
    logger.debug("Loading sensors")
    global ldr_sensors
    
    default_config = await load_default_config()
    sensors_config = await load_sensors_config()
    
    new_sensors = await setup_sensors(default_config, sensors_config)
    ldr_sensors = new_sensors

async def reload_sensors():
    """Reload configuration and update sensors."""
    logger.debug("Reloading sensors")
    
    global ldr_sensors
    
    try:
        default_config = await load_default_config()
        sensors_config = await load_sensors_config()
        
        for sensor_cfg in sensors_config['sensors']:
            sensor_id = sensor_cfg['id']
            
            # Find the matching sensor in the existing list
            existing_sensor = next((ldr for ldr in ldr_sensors if ldr.sensor_id == sensor_id), None)
                
            if existing_sensor:
                # Update the existing sensor's attributes
                existing_sensor.update_sensor(Position(**sensor_cfg['position']), 
                                              sensor_cfg['sampling_period'], 
                                              sensor_cfg['accumulation_window'], 
                                              Plant(**sensor_cfg['plant']))
                logger.debug(f"Updated sensor {sensor_id} with new config.")
                existing_sensor.print_info()
            else:
                # If the sensor doesn't exist, create a new one
                coap_cfg = {"coap_ip": default_config['coap']['ip'], "coap_port": sensor_cfg["coap_port"]}
                mqtt_cfg = default_config['mqtt']
                influxdb_cfg = default_config['influxdb']
                new_sensor = LdrSensorManager(coap_cfg, 
                                              mqtt_cfg, 
                                              influxdb_cfg, 
                                              sensor_id, 
                                              Position(**sensor_cfg['position']), 
                                              Plant(**sensor_cfg['plant']), 
                                              sensor_cfg['sampling_period']
                                              )
                ldr_sensors.append(new_sensor)
                logger.debug(f"Added new sensor {sensor_id}.")
    finally:
        logger.debug("Final config")
        
def welcome_message() -> None:
    """Display a welcome message for the main script."""
    welcome = (
        f"{WHITE}==================================================================={BLUE}\n"
        "\n"
        f"                   Welcome to {BOLD}{RED}S{YELLOW}e{LIME}n{CYAN}s{BLUE}o{MAGENTA}r {RED}P{YELLOW}r{LIME}o{CYAN}x{BLUE}{MAGENTA}y{WHITE}{BLUE}        \n"
        "\n"
        "\033[3mThe script acts as a proxy between the sensors and the database.\n"
        f"To manage the sensors run cli.py.{WHITE}\n"
        f"\n===================================================================\n"
    )
    print(f"{BLUE}{welcome}{WHITE}")


async def main() -> None:
    """Main function to run the server and handle configuration changes."""
    
    welcome_message()
    
    global ldr_sensors
    
    await load_sensors()
    
    loop = asyncio.get_event_loop()
    event_handler = ConfigFileHandler(loop, reload_sensors)
    observer = Observer()
    observer.schedule(event_handler, path='.', recursive=False)
    observer.start()
    
    while True:
        try:
            # Start CoAP servers and MQTT periodic publishing
            await asyncio.gather(
                *[ldr.coap_server() for ldr in ldr_sensors],
                *[ldr.mqtt_client.periodic_publish() for ldr in ldr_sensors],
                reload_sensors()
            )
        except Exception as e:
            logger.error(f"Error occurred: {e}")
        finally:
            observer.stop()
            observer.join()

if __name__ == "__main__":
    asyncio.run(main())
