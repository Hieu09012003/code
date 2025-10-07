#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

//const char* ssid     = "155-157-DHT";
//const char* password = "0935138831";
//const char* ssid     = "LCH";
//const char* password = "11223344";
const char* ssid     = "Nae";
const char* password = "01112003";
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
int redDelay = 10000;
int greenDelay = 10000;
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
d:\PBL5\espdieukhienden_copy_20250916143337\espdieukhienden_copy_20250916143337.ino
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
      client.subscribe("v1/devices/me/rpc/request/+"); // Đăng ký nhận lệnh RPC
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

  StaticJsonDocument<200> doc;
  DeserializationError error = deserializeJson(doc, msg);

  if (error) {
    Serial.print("deserializeJson() failed: ");
    Serial.println(error.c_str());
    return;
  }
  String topicStr = String(topic);
  int lastSlash = topicStr.lastIndexOf('/');
  String requestId = "1";
  if (lastSlash >= 0 && lastSlash + 1 < topicStr.length()) {
    requestId = topicStr.substring(lastSlash + 1);
  }
  String responseTopic = "v1/devices/me/rpc/response/" + requestId;
  // Lấy method và params từ JSON
  const char* method = doc["method"];
  if (method) {
    String m = String(method);
    if (m == "setLight") {
      // read params (can be string or object)
      String color = "";
      if (doc["params"].is<const char*>()) {
        color = String((const char*)doc["params"]);
      } else {
        color = doc["params"].as<String>();
      }
      color.trim();
      color.toUpperCase();

      if (color == "RED" || color == "GREEN" || color == "YELLOW") {
        autoMode = false;
        setLight(color);
        currentColor = color;
        // reply OK
        String responsePayload = String("{\"result\":\"OK, set to ") + color + "\"}";
        client.publish(responseTopic.c_str(), responsePayload.c_str());
        Serial.println("Handled setLight -> " + color);
      } else {
        client.publish(responseTopic.c_str(), "{\"error\":\"invalid param\"}");
      }
    }
    else if (m == "resumeAuto") {
      autoMode = true;
      currentColor = "";
      // reset timing state so auto resumes immediately predictably
      previousMillis = millis();
      currentState = 0;
      setLight("RED"); // start from RED (optional)
      client.publish(responseTopic.c_str(), "{\"result\":\"Switched to AUTO\"}");
      Serial.println("Handled resumeAuto -> back to AUTO");
    }
    else {
      // unknown method
      client.publish(responseTopic.c_str(), "{\"error\":\"unknown method\"}");
    }
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

  if (autoMode) {
    unsigned long currentMillis = millis();
    if (currentState == 0 && currentMillis - previousMillis >= redDelay) {
      setLight("GREEN");
      previousMillis = currentMillis;
      currentState = 1;
    } else if (currentState == 1 && currentMillis - previousMillis >= greenDelay) {
      setLight("YELLOW");
      previousMillis = currentMillis;
      currentState = 2;
    } else if (currentState == 2 && currentMillis - previousMillis >= yellowDelay) {
      setLight("RED");
      previousMillis = currentMillis;
      currentState = 0;
    }
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
  if (color == "RED") payload += "\"traffic_light\":\"🔴\"";
  else if (color == "GREEN") payload += "\"traffic_light\":\"🟢\"";
  else if (color == "YELLOW") payload += "\"traffic_light\":\"🟡\"";

  payload += "}";

  Serial.print("Sending payload: ");
  Serial.println(payload);

  if (client.publish("v1/devices/me/telemetry", (char*) payload.c_str())) {
    Serial.println("Sent OK");
  } else {
    Serial.println("Send FAILED");
  }
}
