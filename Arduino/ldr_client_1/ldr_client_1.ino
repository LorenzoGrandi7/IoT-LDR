#include "WiFi.h"
#include "WiFiUdp.h"
#include "coap-simple.h"
#include "PubSubClient.h"

// #define WIFI_SSID *******
// #define WIFI_PW   *******
// #define COAP_SERVER IPAddress(x, x, x, x)     // Using home Wi-Fi
// #define MQTT_SERVER "192.168.178.78"

#define COAP_PORT 5683
#define MQTT_PORT 1883
#define MQTT_USER "********"
#define MQTT_PASSWORD "********"

#define SAMPLING_PERIOD_TOPIC "home/ldr1/sampling_period"
#define POSITION_TOPIC "home/ldr1/position"

const uint8_t ldr_pin = 0;

WiFiUDP udp;
Coap coap(udp);
WiFiClient espClient;
PubSubClient client(espClient);

int sampling_period = 5000;
String position = "kitchen";

String COAP_URL = "ldrData1";

unsigned long lastSamplingTime = 0;
unsigned long lastMQTTTime = 0;
const unsigned long mqttUpdateInterval = 1000;

// ~~ CoAP ~~
void sendCoapData(String sensor_id, String sensor_position) {
  int ldr_value = analogRead(ldr_pin);
  if (!isnan(ldr_value)) {
    int normalized_ldr_value = map(ldr_value, 0, 4095, 0, 100);
    
    char ldr_str[10];
    snprintf(ldr_str, sizeof(ldr_str), "%d", normalized_ldr_value);

    String sensor_data = "sensor_id=" + sensor_id + "&location=" + sensor_position + "&data=" + ldr_str;
    Serial.println("[LOG] Sending data: " + sensor_data);

    // Serial.print("[DEBUG] Sending CoAP PUT request to ");
    // Serial.print(COAP_SERVER);
    // Serial.print(":");
    // Serial.print(COAP_PORT);
    // Serial.print("/");
    // Serial.println(COAP_URL);

    coap.put(COAP_SERVER, COAP_PORT, COAP_URL.c_str(), sensor_data.c_str());
  } else {
    Serial.println("[ERR] Failed to read LDR");
  }
}

// ~~ MQTT ~~
void mqtt_callback(char *topic, byte *payload, unsigned int length) {
  payload[length] = '\0';
  String message = String((char *)payload);

  // Serial.print("[LOG] MQTT message arrived [");
  // Serial.print(topic);
  // Serial.print("]: ");
  // Serial.println(message);

  if (String(topic) == SAMPLING_PERIOD_TOPIC) {
    int new_sampling_period = message.toInt() * 1000;
    if (new_sampling_period != sampling_period) {
      sampling_period = new_sampling_period;
      Serial.print("[LOG] New sampling period detected: ");
      Serial.println(sampling_period);
    }
  } else if (String(topic) == POSITION_TOPIC) {
    String new_position = message;
    if (new_position != position) {
      position = new_position;
      Serial.println("[LOG] New position detected: "+position);
    }
  }
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("[LOG] Attempting MQTT connection... ");
    if (client.connect("LDR1", MQTT_USER, MQTT_PASSWORD)) {
      Serial.print("Connected to ");
      Serial.println(MQTT_SERVER);
      // Serial.println("[DEB] Subscribing to topics");
      if (client.subscribe(SAMPLING_PERIOD_TOPIC) && client.subscribe(POSITION_TOPIC)) {
        Serial.println("[LOG] Subscription successful.");
      }
      else {
        Serial.println("[ERR] Subscrition failed.");
      }
    } else {
      Serial.print("[ERR] Failed, rc=");
      Serial.print(client.state());
      Serial.println(", try again in 5 seconds");
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  // GPIO pins initialization
  pinMode(ldr_pin, INPUT);

  // WiFi initialization
  WiFi.begin(WIFI_SSID, WIFI_PW);
  Serial.print("[LOG] Connecting to Wi-Fi...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(200);
    Serial.print(".");
  }
  Serial.print("\n[LOG] Connected to Wi-Fi with IP: ");
  Serial.println(WiFi.localIP());

  coap.start();

  client.setServer(MQTT_SERVER, MQTT_PORT);
  client.setKeepAlive(60).setSocketTimeout(60);
  client.setCallback(mqtt_callback);
  if (!client.connected()) {
    reconnect();
  }
  client.loop();
}

void loop() {
  // Differentiated timers to make possible the async changing of sampling period and the sampling transmission
  unsigned long currentTime = millis();

  if (currentTime - lastMQTTTime >= mqttUpdateInterval) {
    lastMQTTTime = currentTime;

    if (!client.connected()) {
      reconnect();
    }
    client.loop();
  }

  if (currentTime - lastSamplingTime >= sampling_period) {
    lastSamplingTime = currentTime;
    sendCoapData("1", position);
  }
}
