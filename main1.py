from ultralytics import YOLO
import cv2
import numpy as np
import json
import os
import paho.mqtt.client as mqtt
from sort.sort import *
from util import get_car, read_license_plate, write_csv

# ============================ #
# ⚙️ CẤU HÌNH MQTT + VIDEO     #
# ============================ #
ACCESS_TOKEN = "1lZGDfQeEZJ7UqV30cTh"   # Token của Raspberry Pi device
BROKER = "demo.thingsboard.io"
PORT = 1883

VIDEO_PATH = "./1000.mp4"
OUTPUT_PATH = "./output_violation.mp4"

# ============================ #
# 📤 GỬI DỮ LIỆU LÊN THINGSBOARD #
# ============================ #
def send_violation(plate_text):
    """Gửi biển số vi phạm lên ThingsBoard"""
    try:
        payload = {
            "plate": plate_text
        }
        client.publish("v1/devices/me/telemetry", json.dumps(payload))
        print(f"🚀 Đã gửi lên ThingsBoard: {payload}")
    except Exception as e:
        print("❌ Lỗi khi gửi dữ liệu lên ThingsBoard:", e)

# ============================ #
# ⚙️ CẤU HÌNH YOLO & SORT      #
# ============================ #
coco_model = YOLO("yolov8n.pt")
license_plate_detector = YOLO("./models/license_plate.pt")
mot_tracker = Sort()

vehicles = [2, 3, 5, 7]  # car, motorcycle, bus, truck
detecting = False         # bật khi có tín hiệu đèn đỏ 🔴

# ============================ #
# 🧭 TỌA ĐỘ VÙNG VI PHẠM       #
# ============================ #
violation_zone = [300, 1550, 3250, 1820]  # [x1, y1, x2, y2]

# ============================ #
# 📊 HÀM TÍNH IOU              #
# ============================ #
def calculate_iou(box, zone):
    xA = max(box[0], zone[0])
    yA = max(box[1], zone[1])
    xB = min(box[2], zone[2])
    yB = min(box[3], zone[3])
    interArea = max(0, xB - xA) * max(0, yB - yA)
    if interArea == 0:
        return 0.0
    boxArea = (box[2] - box[0]) * (box[3] - box[1])
    zoneArea = (zone[2] - zone[0]) * (zone[3] - zone[1])
    iou = interArea / float(boxArea + zoneArea - interArea + 1e-6)
    return iou

# ============================ #
# 🧠 XỬ LÝ VIDEO CHÍNH         #
# ============================ #
def process_video():
    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print("❌ Không thể mở video!")
        return

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out = cv2.VideoWriter(OUTPUT_PATH, fourcc, fps, (width, height))

    # Tạo thư mục lưu biển số
    os.makedirs("violations", exist_ok=True)

    frame_nmr = 0
    results = {}

    print(f"📹 Video {width}x{height} @ {fps}fps")

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_nmr += 1
        results[frame_nmr] = {}

        # 1️⃣ PHÁT HIỆN XE
        detections = coco_model(frame, conf=0.3)[0]
        detections_ = []
        for det in detections.boxes.data.tolist():
            x1, y1, x2, y2, score, class_id = det
            if int(class_id) in vehicles:
                detections_.append([x1, y1, x2, y2, score])

        # 2️⃣ TRACKING (SORT)
        if len(detections_) > 0:
            track_ids = mot_tracker.update(np.asarray(detections_))
        else:
            track_ids = mot_tracker.update(np.empty((0, 5)))

        # 3️⃣ VẼ VÙNG VI PHẠM
        cv2.rectangle(frame, (violation_zone[0], violation_zone[1]),
                      (violation_zone[2], violation_zone[3]), (0, 0, 255), 3)
        cv2.putText(frame, "Violation Zone",
                    (violation_zone[0], violation_zone[1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        # 4️⃣ KIỂM TRA TỪNG XE
        for track in track_ids:
            x1, y1, x2, y2, track_id = track
            car_box = [x1, y1, x2, y2]
            iou = calculate_iou(car_box, violation_zone)

            if detecting and iou > 0.1:
                # 🚨 XE VI PHẠM
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 3)
                cv2.putText(frame, f"VIOLATION #{int(track_id)}",
                            (int(x1), int(y1) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                            (0, 0, 255), 2)

                # 5️⃣ NHẬN DIỆN BIỂN SỐ
                license_plates = license_plate_detector(frame)[0]
                for license_plate in license_plates.boxes.data.tolist():
                    lx1, ly1, lx2, ly2, score, class_id = license_plate
                    xcar1, ycar1, xcar2, ycar2, car_id = get_car(license_plate, track_ids)

                    if car_id == track_id:
                        license_plate_crop = frame[int(ly1):int(ly2), int(lx1):int(lx2), :]
                        if license_plate_crop.size == 0:
                            continue

                        # Chuyển sang grayscale và threshold
                        license_plate_crop_gray = cv2.cvtColor(license_plate_crop, cv2.COLOR_BGR2GRAY)
                        _, license_plate_crop_thresh = cv2.threshold(license_plate_crop_gray, 64, 255, cv2.THRESH_BINARY_INV)
                        license_plate_text, license_plate_text_score = read_license_plate(license_plate_crop_thresh)

                        if license_plate_text:
                            # 🖼️ Lưu ảnh biển số
                            filename = f"violations/frame{frame_nmr}_id{int(track_id)}_{license_plate_text}.jpg"
                            cv2.imwrite(filename, license_plate_crop)
                            print(f"💾 Lưu ảnh biển số: {filename}")

                            # Ghi dữ liệu vào dict
                            results[frame_nmr][car_id] = {
                                "car": {"bbox": [xcar1, ycar1, xcar2, ycar2]},
                                "license_plate": {"bbox": [lx1, ly1, lx2, ly2],
                                                  "text": license_plate_text,
                                                  "bbox_score": score,
                                                  "text_score": license_plate_text_score}
                            }

                            # Hiển thị lên video
                            cv2.putText(frame, license_plate_text, (int(lx1), int(ly1) - 10),
                                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
                            cv2.rectangle(frame, (int(lx1), int(ly1)),
                                          (int(lx2), int(ly2)), (255, 0, 0), 2)
                            print(f"✅ [Frame {frame_nmr}] Xe #{track_id} - Biển: {license_plate_text}")
                            send_violation(license_plate_text)


            else:
                # 🟢 XE HỢP LỆ
                cv2.rectangle(frame, (int(x1), int(y1)),
                              (int(x2), int(y2)), (0, 255, 0), 2)
                cv2.putText(frame, f"ID {int(track_id)}", (int(x1), int(y1) - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # 6️⃣ HIỂN THỊ VIDEO
        frame_disp = cv2.resize(frame, (1280, 720))
        cv2.imshow("Traffic Monitoring - Violation Detection", frame_disp)
        out.write(frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    write_csv(results, "./violation_results.csv")
    cap.release()
    out.release()
    cv2.destroyAllWindows()

# ============================ #
# 🔔 MQTT CALLBACKS             #
# ============================ #
def on_connect(client, userdata, flags, rc):
    print("✅ Kết nối ThingsBoard thành công!" if rc == 0 else f"❌ Lỗi kết nối: {rc}")
    client.subscribe("v1/devices/me/rpc/request/+")

def on_message(client, userdata, msg):
    global detecting
    payload = msg.payload.decode("utf-8")
    print(f"[MQTT] Topic: {msg.topic} | {payload}")

    try:
        data = json.loads(payload)
        # ✅ RPC từ ThingsBoard có dạng {"method":"setLight","params":"RED"}
        if "method" in data and data["method"] == "setLight":
            color = data.get("params", "").upper()

            if color == "RED":
                detecting = True
                print("🚨 ĐÈN ĐỎ - BẮT ĐẦU NHẬN DIỆN VI PHẠM")
            else:
                detecting = False
                print(f"🟢 ĐÈN {color} - DỪNG NHẬN DIỆN")
        else:
            print("⚠️ RPC không khớp hoặc không hợp lệ.")
    except Exception as e:
        print("⚠️ Lỗi xử lý MQTT:", e)

# ============================ #
# 🏁 CHẠY CHƯƠNG TRÌNH CHÍNH   #
# ============================ #
if __name__ == "__main__":
    client = mqtt.Client()
    client.username_pw_set(ACCESS_TOKEN)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT, 60)

    client.loop_start()
    process_video()
    client.loop_stop()
