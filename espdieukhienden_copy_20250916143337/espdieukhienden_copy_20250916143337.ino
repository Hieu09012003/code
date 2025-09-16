#include <WiFi.h>
#include <PubSubClient.h>

//const char* ssid     = "155-157-DHT";
//const char* password = "0935138831";
const char* ssid     = "LCH";
const char* password = "11223344";
const char* mqtt_server = "demo.thingsboard.io";  // Thay bằng IP nếu bạn chạy server local
const int mqtt_port = 1883;
const char* accessToken = "VbAuoKsMiCdK2aDU6GD4"; // Device Token trên ThingsBoard

WiFiClient espClient;
PubSubClient client(espClient);

// Chân LED đèn giao thông (Red, Yellow, Green)
const int redPin = 26;
const int yellowPin = 25;
const int greenPin = 33;

// Thời gian delay (ms)
int redDelay = 30000;
int greenDelay = 30000;
int yellowDelay = 3000;
bool autoMode = true;  // true = Auto, false = Manual
void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("");
  Serial.println("WiFi connected");
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Connecting to ThingsBoard...");
    if (client.connect("ESP32TrafficLight", accessToken, NULL)) {
      Serial.println("connected");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 5s");
      delay(5000);
    }
  }
}
void callback(char* topic, byte* payload, unsigned int length) {
  String msg;
  for (unsigned int i = 0; i < length; i++) {
    msg += (char)payload[i];
  }
  Serial.print("Received RPC: ");
  Serial.println(msg);

  // Nếu nhấn Resume Auto → quay lại Auto mode
  if (msg.indexOf("Resume Auto") != -1) {
    autoMode = true;
    Serial.println("Switched to AUTO mode");
    return;
  }

  // Nếu Manual → bật đèn theo lệnh
  autoMode = false;
  if (msg.indexOf("RED") != -1) {
    setLight("RED");
  } else if (msg.indexOf("GREEN") != -1) {
    setLight("GREEN");
  } else if (msg.indexOf("YELLOW") != -1) {
    setLight("YELLOW");
  }
}
void setup() {
  Serial.begin(115200);
  pinMode(redPin, OUTPUT);
  pinMode(yellowPin, OUTPUT);
  pinMode(greenPin, OUTPUT);

  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();
  if (autoMode) {
    // RED
    setLight("RED");
    delay(redDelay);

    // GREEN
    setLight("GREEN");
    delay(greenDelay);

    // YELLOW
    setLight("YELLOW");
    delay(yellowDelay);
  }
}
  void setLight(String color) {
  if (color == "RED") {
    digitalWrite(redPin, HIGH);
    digitalWrite(yellowPin, LOW);
    digitalWrite(greenPin, LOW);} 
    else if (color == "GREEN") {
    digitalWrite(redPin, LOW);
    digitalWrite(yellowPin, LOW);
    digitalWrite(greenPin, HIGH);}
    else if (color == "YELLOW") {
    digitalWrite(redPin, LOW);
    digitalWrite(yellowPin, HIGH);
    digitalWrite(greenPin, LOW);
  }

  sendStatus(color);
}

void sendStatus(String color) {
  String payload = "{";
  if (color == "RED") payload += "\"traffic_light\":\"RED\"";
  else if (color == "GREEN") payload += "\"traffic_light\":\"GREEN\"";
  else if (color == "YELLOW") payload += "\"traffic_light\":\"YELLOW\"";

  payload += "}";

  Serial.print("Sending payload: ");
  Serial.println(payload);

  if (client.publish("v1/devices/me/telemetry", (char*) payload.c_str())) {
    Serial.println("Sent OK");
  } else {
    Serial.println("Send FAILED");
  }
}

