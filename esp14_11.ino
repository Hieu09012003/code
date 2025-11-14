#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
//#include <ThingsBoard.h>

//const char* ssid     = "155-157-DHT";
//const char* password = "0935138831";
const char* ssid     = "LCH";
const char* password = "11223344";
//const char* ssid     = "Nae";
//const char* password = "01112003";
const char* mqtt_server = "demo.thingsboard.io";  // Thay bằng IP nếu bạn chạy server local
const int mqtt_port = 1883;
const char* accessToken = "VbAuoKsMiCdK2aDU6GD4"; // Device Token trên ThingsBoard

WiFiClient espClient;
PubSubClient client(espClient);
//ThingsBoard tb(mqttClient);

// Chân LED đèn giao thông (Red, Yellow, Green)
const int redPin = 26;
const int yellowPin = 25;
const int greenPin = 33;

// Thời gian delay (ms)
int redDelay = 20000;
int greenDelay = 5000;
int yellowDelay = 5000;

bool autoMode = true;  // true = Auto, false = Manual
String currentColor = "";
unsigned long previousMillis = 0;
int currentState = 0; // 0 = RED, 1 = GREEN, 2 = YELLOW 
void setLight(String color);
void sendStatus(String color);
void reconnect();
void callback(char* topic, byte* payload, unsigned int length);
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
      client.subscribe("v1/devices/me/rpc/request/+");
      client.subscribe("v1/devices/me/attributes");  // Đăng ký nhận lệnh RPC
      client.publish("v1/devices/me/attributes/request/1", "{\"sharedKeys\":\"mode\"}");
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
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];

  Serial.print("Received RPC: ");
  Serial.println(msg);

  StaticJsonDocument<256> doc;
  if (deserializeJson(doc, msg)) return;

  // Case 1: {"shared":{"mode":"xxx"}}
  if (doc.containsKey("shared")) {
    if (doc["shared"].containsKey("mode")) {
      processMode(doc["shared"]["mode"].as<String>());
    }
  } 
  // Case 2: {"mode":"xxx"}
  else if (doc.containsKey("mode")) {
    processMode(doc["mode"].as<String>());
  }
}

void processMode(String mode) {
  mode.toUpperCase();
  Serial.print("Process mode = ");
  Serial.println(mode);

  if (mode == "AUTO") {
    autoMode = true;
    currentState = 0;
    previousMillis = millis();
    setLight("RED");
  } 
  else if (mode == "MANUAL_RED") {
    autoMode = false;
    currentState = -1;
    setLight("RED");
  }
  else if (mode == "MANUAL_GREEN") {
    autoMode = false;
    currentState = -1;
    setLight("GREEN");
  }
  else if (mode == "MANUAL_YELLOW") {
    autoMode = false;
    currentState = -1;
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

  setLight("RED");
  previousMillis = millis();
  currentState = 0;
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  if (!autoMode) {
    return; // thoát loop, không chạy auto nữa
  }

  unsigned long currentMillis = millis();

  if (currentState == 0 && currentMillis - previousMillis >= redDelay) {
    setLight("GREEN");
    previousMillis = currentMillis;
    currentState = 1;
  } 
  else if (currentState == 1 && currentMillis - previousMillis >= greenDelay) {
    setLight("YELLOW");
    previousMillis = currentMillis;
    currentState = 2;
  } 
  else if (currentState == 2 && currentMillis - previousMillis >= yellowDelay) {
    setLight("RED");
    previousMillis = currentMillis;
    currentState = 0;
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
  String emoji;
  String colorText;
  
  if (color == "RED") { emoji = "🔴"; colorText = "red"; }
  else if (color == "GREEN") { emoji = "🟢"; colorText = "green"; }
  else if (color == "YELLOW") { emoji = "🟡"; colorText = "yellow"; }

  String payload = "{\"traffic_light\":\"" + emoji + "\", \"light_color\":\"" + colorText + "\"}";
  
  Serial.print("Sending payload: ");
  Serial.println(payload);

  if (client.publish("v1/devices/me/telemetry", payload.c_str())) {
    Serial.println("Sent OK ");
  } else {
    Serial.println("Send FAILED ");
  }
  client.publish("v1/devices/me/attributes", ("{\"current_light\":\"" + colorText + "\"}").c_str());

}
