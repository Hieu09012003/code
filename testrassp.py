import paho.mqtt.client as mqtt
import json
import time
import threading

# ====== ThingsBoard Device Credentials ======
THINGSBOARD_HOST = "demo.thingsboard.io"
ACCESS_TOKEN = "VbAuoKsMiCdK2aDU6GD4"   # <-- Token của ESP32 device
PORT = 1883

# ====== Các trạng thái nhận diện ======
detecting = False
stop_thread = False

# ====== Giả lập hàm nhận diện (bạn thay bằng code OpenCV sau này) ======
def start_violation_detection():
    global detecting, stop_thread
    if detecting:
        print("🚫 Nhận diện đã chạy, bỏ qua...")
        return

    detecting = True
    stop_thread = False

    def detect_loop():
        print("🚗 Bắt đầu nhận diện vi phạm (đèn đỏ ON)...")
        while not stop_thread:
            # Giả lập xử lý ảnh — sau này thay bằng code OpenCV của bạn
            print("🔍 Đang kiểm tra camera...")
            time.sleep(2)
        print("✅ Đã dừng nhận diện vi phạm.")

    t = threading.Thread(target=detect_loop)
    t.start()


def stop_violation_detection():
    global detecting, stop_thread
    if not detecting:
        print("🟢 Nhận diện chưa chạy.")
        return
    stop_thread = True
    detecting = False
    print("🟢 Dừng nhận diện (đèn xanh).")

# ====== Xử lý khi nhận được message từ ThingsBoard ======
def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        print(f"📩 Nhận telemetry: {payload}")

        traffic_light = payload.get("traffic_light", "")

        if traffic_light == "🔴":
            start_violation_detection()
        elif traffic_light == "🟢":
            stop_violation_detection()
        elif traffic_light == "🟡":
            print("🟡 Đèn vàng - chờ chuyển pha.")
        else:
            print("⚠️ Không xác định tín hiệu.")
    except Exception as e:
        print("❌ Lỗi xử lý message:", e)

# ====== Kết nối MQTT ======
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Kết nối ThingsBoard thành công!")
        # Subscribe telemetry topic của device
        client.subscribe("v1/devices/me/telemetry")
    else:
        print("❌ Lỗi kết nối MQTT. Mã lỗi:", rc)

# ====== Main ======
def main():
    client = mqtt.Client()
    client.username_pw_set(ACCESS_TOKEN)
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(THINGSBOARD_HOST, PORT, 60)
    client.loop_forever()

if __name__ == "__main__":
    main()
