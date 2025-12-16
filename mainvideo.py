from ultralytics import YOLO
import cv2
import numpy as np
import json
import os
import csv
from sort.sort import *
# 🚀 IMPORT: Dùng hàm đọc trực tiếp từ module nhận diện
from lp_reader import read_license_plate_direct 

# ============================ #
# ⚙️ CẤU HÌNH VIDEO & THƯ MỤC   #
# ============================ #
VIDEO_PATH = "./1000.mp4"
OUTPUT_PATH = "./output_violation_final_fixed.mp4" 

VIOLATION_DIR = "Results_violation_always_red"
SUMMARY_OUTPUT_PATH = "./violation_summary_always_red.csv"

# --- 🔥 CẤU HÌNH QUAN TRỌNG (ĐÃ SỬA ĐỂ FIX LỖI E1->A5) ---
# 1. Ảnh dùng để TRÍCH XUẤT (OCR)
# Mức 0.2 (20%) là mức vàng: Đủ để lấy hết biển số nhưng loại bỏ được ốc vít và viền đen.
# Khắc phục triệt để lỗi E->A (do bóng viền) và 1->5 (do dính ốc vít).
PLATE_EXPANSION_FACTOR = 0.2   

# 2. Ảnh BẰNG CHỨNG (Toàn cảnh)
# Giữ 0.6 (60%) để ảnh bằng chứng nhìn rộng rãi, rõ bối cảnh.
FULL_VIEW_EXPAND_RATIO = 0.6    

# ============================ #
# ⚙️ CẤU HÌNH YOLO & SORT       #
# ============================ #
coco_model = YOLO("yolov8n.pt")
license_plate_detector = YOLO("./models/license_plate.pt")
mot_tracker = Sort()

vehicles = [2, 3, 5, 7]  # car, motorcycle, bus, truck
DETECT_VIOLATION = True         

# ============================ #
# 🧭 TỌA ĐỘ VÙNG VI PHẠM      #
# ============================ #
violation_zone = [1000, 1450, 2850, 1750]  # [x1, y1, x2, y2]

# ============================ #
# 🛠️ HÀM HẬU XỬ LÝ (VERSION 5) #
# ============================ #
def post_process_plate(plate_str):
    """
    Sửa lỗi nhận diện V5 (Tối ưu cho mức cắt 0.2):
    1. Fix lỗi địa phương: 03 -> 43 (do cảm biến), K -> A.
    2. Xóa ký tự rác đầu (C43 -> 43).
    3. Cắt bỏ ký tự thừa ở giữa (nếu có).
    """
    if not plate_str or len(plate_str) < 4:
        return plate_str
        
    chars = list(plate_str)
    
    # --- BƯỚC 1: MAPPING SƠ BỘ (Chữ -> Số cho Mã Tỉnh) ---
    char_to_num = {'B': '8', 'D': '0', 'O': '0', 'I': '1', 'Z': '2', 'S': '5', 'G': '6', 'Q': '0', 'A': '4'}
    for i in range(min(2, len(chars))):
        if chars[i] in char_to_num:
            chars[i] = char_to_num[chars[i]]

    # --- BƯỚC 2: XÓA KÝ TỰ RÁC Ở ĐẦU ---
    # Nếu ký tự đầu là Chữ, ký tự 2 là Số -> Xóa đầu (VD: C43 -> 43)
    if len(chars) > 2:
        if not chars[0].isdigit() and chars[1].isdigit():
            chars.pop(0)

    # --- BƯỚC 3: SỬA LỖI ĐỊA PHƯƠNG ---
    # Fix lỗi 43 (Đà Nẵng) bị đọc thành 03 do cảm biến
    if len(chars) > 1:
        if chars[0] == '0' and chars[1] == '3':
            chars[0] = '4' 

    # --- BƯỚC 4: XỬ LÝ ĐỘ DÀI ---
    # Biển 5 số chuẩn max là 9 ký tự. Nếu dài hơn, xóa ký tự thừa ở giữa.
    if len(chars) > 9:
        if len(chars) > 3 and chars[2].isalpha() and chars[3].isdigit():
             chars.pop(3)

    # --- BƯỚC 5: SỬA LỖI SERIES (KÝ TỰ THỨ 3) ---
    num_to_char = {'4': 'A', '8': 'B', '0': 'D', '1': 'I', '2': 'Z', '5': 'S', '6': 'G', '7': 'Z'}
    
    if len(chars) > 2:
        # Ép số thành chữ
        if chars[2] in num_to_char:
            chars[2] = num_to_char[chars[2]]
        
        # Heuristic: Biển xe con 43 thường là A. Nếu nhận là K (do bóng mờ), ép về A.
        if chars[0] == '4' and chars[1] == '3' and chars[2] == 'K':
            chars[2] = 'A'

    return "".join(chars)

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
# 💾 HÀM GHI TÓM TẮT CSV       #
# ============================ #
def write_violation_summary_csv(violation_records, summary_output_path):
    violated_plates = {}
    for record in violation_records:
        plate_final = record['plate_final']
        if plate_final and plate_final not in violated_plates:
            violated_plates[plate_final] = {
                'first_seen_frame': record['frame_nmr'],
                'track_id': record['track_id'],
                'plate_raw': record['plate_raw'],
                'plate_type': record['plate_type'] 
            }

    with open(summary_output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['license_number_final', 'license_number_raw', 'license_number_type', 'track_id', 'first_seen_frame'])
        
        for plate_final, info in violated_plates.items():
            writer.writerow([plate_final, info['plate_raw'], info['plate_type'], info['track_id'], info['first_seen_frame']])

# ============================ #
# 🧠 XỬ LÝ VIDEO CHÍNH        #
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

    # --- TẠO 3 THƯ MỤC LƯU TRỮ ---
    LP_DIR = os.path.join(VIOLATION_DIR, "BienSo")        # Ảnh biển số (OCR) - Cắt sát
    FULL_DIR = os.path.join(VIOLATION_DIR, "ToanCanh")    # Ảnh toàn cảnh - Cắt rộng
    OCR_DIR = os.path.join(VIOLATION_DIR, "AnhDauVaoOCR") # Ảnh debug OCR
    
    os.makedirs(LP_DIR, exist_ok=True)
    os.makedirs(FULL_DIR, exist_ok=True)
    os.makedirs(OCR_DIR, exist_ok=True)
    
    print(f"📁 Cấu hình hệ thống:")
    print(f"   - OCR Crop Padding: {PLATE_EXPANSION_FACTOR*100}% (Sát, chống nhiễu)")
    print(f"   - Evidence Padding: {FULL_VIEW_EXPAND_RATIO*100}% (Rộng, toàn cảnh)")

    frame_nmr = 0
    captured_track_ids = set() 
    violation_records = []

    print(f"📹 Bắt đầu xử lý video...")

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_nmr += 1
        
        clean_frame = frame.copy() 

        # 1. PHÁT HIỆN XE & TRACKING
        detections = coco_model(frame, conf=0.1)[0]
        detections_ = []
        for det in detections.boxes.data.tolist():
            x1, y1, x2, y2, score, class_id = det
            if int(class_id) in vehicles:
                detections_.append([x1, y1, x2, y2, score])
        
        if len(detections_) > 0:
            track_ids = mot_tracker.update(np.asarray(detections_))
        else:
            track_ids = mot_tracker.update(np.empty((0, 5)))

        # 2. VẼ VÙNG VI PHẠM
        cv2.rectangle(frame, (violation_zone[0], violation_zone[1]),
                      (violation_zone[2], violation_zone[3]), (0, 0, 255), 3)

        license_plates = None 

        # 3. KIỂM TRA VI PHẠM
        for track in track_ids:
            x1, y1, x2, y2, track_id = track
            car_box = [x1, y1, x2, y2]
            iou = calculate_iou(car_box, violation_zone)
            current_track_id = int(track_id)

            if DETECT_VIOLATION and iou > 0.08 and current_track_id not in captured_track_ids:
                
                # Cảnh báo
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 3)
                cv2.putText(frame, f"VIOLATION #{current_track_id}",
                            (int(x1), int(y1) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                
                # 4. PHÁT HIỆN BIỂN SỐ
                if license_plates is None:
                    license_plates = license_plate_detector(clean_frame)[0] 
                
                for license_plate in license_plates.boxes.data.tolist():
                    lx1, ly1, lx2, ly2, score, class_id = license_plate
                    
                    # --- A. CẮT BIỂN SỐ ĐỂ TRÍCH XUẤT (Dùng Factor 0.2) ---
                    lp_width = lx2 - lx1
                    lp_height = ly2 - ly1
                    expand_x = lp_width * PLATE_EXPANSION_FACTOR
                    expand_y = lp_height * PLATE_EXPANSION_FACTOR
                    
                    expanded_lx1 = max(0, int(lx1 - expand_x))
                    expanded_ly1 = max(0, int(ly1 - expand_y))
                    expanded_lx2 = min(width, int(lx2 + expand_x))
                    expanded_ly2 = min(height, int(ly2 + expand_y))
                    
                    # Ảnh OCR (Sạch, ít nhiễu)
                    license_plate_crop = clean_frame[expanded_ly1:expanded_ly2, expanded_lx1:expanded_lx2, :]
                    
                    if license_plate_crop.size > 0:
                        # --- B. NHẬN DIỆN & HẬU XỬ LÝ ---
                        recognition_result = read_license_plate_direct(license_plate_crop)
                        plate_raw_text = recognition_result.plate() 
                        
                        # 🔥 Sửa lỗi thông minh V5
                        plate_final = post_process_plate(plate_raw_text)
                        
                        try:
                            plate_type = recognition_result.type_str()
                        except AttributeError:
                            plate_type = ""

                        # --- C. CẮT ẢNH TOÀN CẢNH (Dùng Ratio 0.6) ---
                        veh_w = x2 - x1
                        veh_h = y2 - y1
                        pad_w = int(veh_w * FULL_VIEW_EXPAND_RATIO)
                        pad_h = int(veh_h * FULL_VIEW_EXPAND_RATIO)
                        
                        env_x1 = max(0, int(x1 - pad_w))
                        env_y1 = max(0, int(y1 - pad_h))
                        env_x2 = min(width, int(x2 + pad_w))
                        env_y2 = min(height, int(y2 + pad_h))
                        
                        # Ảnh Bằng Chứng (Rộng)
                        vehicle_crop_expanded = clean_frame[env_y1:env_y2, env_x1:env_x2].copy()

                        # --- D. LƯU FILE ---
                        if plate_final:
                            base_name = f"{plate_final}"
                        else:
                            base_name = f"unknown_frame{frame_nmr}_id{current_track_id}"

                        # 1. Ảnh biển số
                        lp_filename = f"{LP_DIR}/{base_name}_LP.jpg"
                        cv2.imwrite(lp_filename, license_plate_crop)

                        # 2. Ảnh toàn cảnh
                        car_filename = f"{FULL_DIR}/{base_name}_FULL.jpg"
                        if vehicle_crop_expanded.size > 0:
                            cv2.imwrite(car_filename, vehicle_crop_expanded)
                            
                        # 3. Ảnh debug OCR
                        ocr_input_filename = f"{OCR_DIR}/{base_name}_OCR_Input.jpg"
                        cv2.imwrite(ocr_input_filename, license_plate_crop)
                        
                        # -----------------------------------------------------
                        captured_track_ids.add(current_track_id) 

                        violation_records.append({
                            'plate_final': plate_final,
                            'plate_raw': plate_raw_text, 
                            'plate_type': plate_type, 
                            'track_id': current_track_id,
                            'frame_nmr': frame_nmr
                        })
                        
                        print(f"💾 [Frame {frame_nmr}] Xe #{current_track_id} -> Kết quả: {plate_final} (Raw: {plate_raw_text})")
                        
                        cv2.rectangle(frame, (expanded_lx1, expanded_ly1), (expanded_lx2, expanded_ly2), (255, 0, 0), 2)
                        
                        break 
            
            else:
                # XE HỢP LỆ
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                cv2.putText(frame, f"ID {int(track_id)}", (int(x1), int(y1) - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # 5. HIỂN THỊ VÀ GHI VIDEO
        frame_disp = cv2.resize(frame, (1280, 720))
        cv2.imshow("Traffic Monitoring", frame_disp)
        out.write(frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # 6. KẾT THÚC
    print(f"Hoàn tất. Tổng số xe vi phạm: {len(captured_track_ids)}")
    cap.release()
    out.release()
    cv2.destroyAllWindows()
    
    write_violation_summary_csv(violation_records, SUMMARY_OUTPUT_PATH)
    print(f"✅ Đã xuất file báo cáo: {SUMMARY_OUTPUT_PATH}")

if __name__ == "__main__":
    process_video()