import paho.mqtt.client as mqtt
import json
import time

# Token của thiết bị Raspberry Pi
ACCESS_TOKEN = "1lZGDfQeEZJ7UqV30cTh"
BROKER = "demo.thingsboard.io"
PORT = 1883

def on_connect(client, userdata, flags, rc):
    print("Kết nối ThingsBoard thành công!" if rc == 0 else f"Lỗi kết nối: {rc}")
    # Đăng ký nhận shared attribute từ ESP32 (nếu bạn đã chia sẻ)
    client.subscribe("v1/devices/me/attributes")
    # Đăng ký nhận RPC từ dashboard
    client.subscribe("v1/devices/me/rpc/request/+")
    print("Đang lắng nghe topic...")

def on_message(client, userdata, msg):
    print(f"Nhận topic: {msg.topic}")
    payload = msg.payload.decode('utf-8')
    print(f"Nội dung: {payload}")

    try:
        data = json.loads(payload)
        if "method" in data and data["method"] == "camera_action":
            color = data["params"]["traffic_light"]
            print(f"==> Đèn hiện tại: {color}")
            if color == "🔴":
                print("🚨 Bắt đầu nhận diện vi phạm!")
                # run_license_plate_detection()
            else:
                print("🟢🟡 Dừng nhận diện, đèn không đỏ.")
    except Exception as e:
        print("Lỗi xử lý dữ liệu:", e)
    
    

client = mqtt.Client()
client.username_pw_set(ACCESS_TOKEN)
client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT, 60)
client.loop_forever()




