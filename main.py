from ultralytics import YOLO
import cv2
import numpy as np

import util
from sort.sort import *
from util import get_car, read_license_plate, write_csv

results = {}

mot_tracker = Sort()

# load models
coco_model = YOLO('yolov8x.pt')
license_plate_detector = YOLO('./models/license_plate.pt')

# load video
cap = cv2.VideoCapture('./0923.mp4')

# ---- thêm phần khởi tạo VideoWriter ----
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
fps = cap.get(cv2.CAP_PROP_FPS)
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
out = cv2.VideoWriter('./output_video.mp4', fourcc, fps, (width, height))

vehicles = [2, 3]

# read frames
frame_nmr = -1
ret = True
while ret and frame_nmr < 1000: 
    frame_nmr += 1
    ret, frame = cap.read()
    if not ret:
        break

    results[frame_nmr] = {}
    # detect vehicles
    detections = coco_model(frame, conf=0.25)[0]
    detections_ = []
    for detection in detections.boxes.data.tolist():
        x1, y1, x2, y2, score, class_id = detection
        #print("Detected:", coco_model.names[int(class_id)], "Score:", score)  # in class name
        if int(class_id) in vehicles:
            detections_.append([x1, y1, x2, y2, score])


    # track vehicles
    if len(detections_) > 0:
        track_ids = mot_tracker.update(np.asarray(detections_))
    else:
        track_ids = mot_tracker.update(np.empty((0, 5)))

    # detect license plates
    license_plates = license_plate_detector(frame)[0]
    for license_plate in license_plates.boxes.data.tolist():
        x1, y1, x2, y2, score, class_id = license_plate

        # assign license plate to car
        xcar1, ycar1, xcar2, ycar2, car_id = get_car(license_plate, track_ids)

        if car_id != -1:
            # crop license plate
            license_plate_crop = frame[int(y1):int(y2), int(x1): int(x2), :]

            # process license plate
            license_plate_crop_gray = cv2.cvtColor(license_plate_crop, cv2.COLOR_BGR2GRAY)
            _, license_plate_crop_thresh = cv2.threshold(license_plate_crop_gray, 64, 255, cv2.THRESH_BINARY_INV)

            # read license plate number
            license_plate_text, license_plate_text_score = read_license_plate(license_plate_crop_thresh)

            if license_plate_text is not None:
                results[frame_nmr][car_id] = {
                    'car': {'bbox': [xcar1, ycar1, xcar2, ycar2]},
                    'license_plate': {'bbox': [x1, y1, x2, y2],
                                      'text': license_plate_text,
                                      'bbox_score': score,
                                      'text_score': license_plate_text_score}
                }

                # ---- vẽ lên frame ----
                cv2.rectangle(frame, (int(xcar1), int(ycar1)), (int(xcar2), int(ycar2)), (0, 255, 0), 2)
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 2)
                cv2.putText(frame, license_plate_text, (int(x1), int(y1) - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)

    # ---- ghi frame đã vẽ ra video ----
    out.write(frame)

# write results CSV
write_csv(results, './test3.csv')

cap.release()
out.release()
cv2.destroyAllWindows()


