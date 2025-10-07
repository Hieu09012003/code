import string
import easyocr

# Initialize the OCR reader
reader = easyocr.Reader(['en'], gpu=False)  # Có thể thử ['vi'] nếu EasyOCR hỗ trợ tiếng Việt tốt hơn, nhưng 'en' thường ổn cho số/chữ.

# Mapping dictionaries for character conversion (giữ nguyên, phù hợp cho OCR errors phổ biến)
dict_char_to_int = {'O': '0',
                    'I': '1',
                    'J': '3',
                    'A': '4',
                    'G': '6',
                    'S': '5'}

dict_int_to_char = {'0': 'O',
                    '1': 'I',
                    '3': 'J',
                    '4': 'A',
                    '6': 'G',
                    '5': 'S'}

def write_csv(results, output_path):
    """
    Write the results to a CSV file.

    Args:
        results (dict): Dictionary containing the results.
        output_path (str): Path to the output CSV file.
    """
    with open(output_path, 'w') as f:
        f.write('{},{},{},{},{},{},{}\n'.format('frame_nmr', 'car_id', 'car_bbox',
                                                'license_plate_bbox', 'license_plate_bbox_score', 'license_number',
                                                'license_number_score'))

        for frame_nmr in results.keys():
            for car_id in results[frame_nmr].keys():
                print(results[frame_nmr][car_id])
                if 'car' in results[frame_nmr][car_id].keys() and \
                   'license_plate' in results[frame_nmr][car_id].keys() and \
                   'text' in results[frame_nmr][car_id]['license_plate'].keys():
                    f.write('{},{},{},{},{},{},{}\n'.format(frame_nmr,
                                                            car_id,
                                                            '[{} {} {} {}]'.format(
                                                                results[frame_nmr][car_id]['car']['bbox'][0],
                                                                results[frame_nmr][car_id]['car']['bbox'][1],
                                                                results[frame_nmr][car_id]['car']['bbox'][2],
                                                                results[frame_nmr][car_id]['car']['bbox'][3]),
                                                            '[{} {} {} {}]'.format(
                                                                results[frame_nmr][car_id]['license_plate']['bbox'][0],
                                                                results[frame_nmr][car_id]['license_plate']['bbox'][1],
                                                                results[frame_nmr][car_id]['license_plate']['bbox'][2],
                                                                results[frame_nmr][car_id]['license_plate']['bbox'][3]),
                                                            results[frame_nmr][car_id]['license_plate']['bbox_score'],
                                                            results[frame_nmr][car_id]['license_plate']['text'],
                                                            results[frame_nmr][car_id]['license_plate']['text_score'])
                            )
        f.close()

def license_complies_format(text):
    """
    Check if the license plate text complies with the required format for Vietnamese square plates.

    Args:
        text (str): License plate text.

    Returns:
        bool: True if the license plate complies with the format, False otherwise.
    """
    if len(text) < 8 or len(text) > 10:
        return False

    # Format cơ bản cho VN: 2 số đầu (tỉnh), chữ cái (series), số còn lại.
    # Ví dụ: "59F112345" (len=9)
    # Kiểm tra linh hoạt: 2 ký tự đầu là số, có ít nhất 1 chữ cái ở giữa, còn lại chủ yếu số.

    # Vị trí 0-1: số (hoặc convert từ char)
    if not (text[0] in string.digits or text[0] in dict_char_to_int):
        return False
    if not (text[1] in string.digits or text[1] in dict_char_to_int):
        return False

    # Có ít nhất một chữ cái ở vị trí 2-3
    if not (text[2] in string.ascii_uppercase or text[2] in dict_int_to_char):
        return False
    if not (text[3] in string.digits or text[3] in dict_char_to_int):
        return False

    # Còn lại nên là số (cho phép convert)
    for c in text[4:]:
        if not (c in string.digits or c in dict_char_to_int):
            return False

    return True

def format_license(text):
    """
    Format the license plate text by converting characters using the mapping dictionaries for VN format.

    Args:
        text (str): License plate text.

    Returns:
        str: Formatted license plate text.
    """
    license_plate_ = ''
    # Mapping vị trí cho VN: vị trí số (0,1,3-end): char_to_int; vị trí chữ (2, có thể 3): int_to_char
    mapping = {0: dict_char_to_int, 1: dict_char_to_int, 
               2: dict_int_to_char, 3: dict_int_to_char}  # 3 có thể là chữ hoặc số, apply both possible
    for j in range(len(text)):
        if j in mapping:
            if text[j] in mapping[j]:
                license_plate_ += mapping[j][text[j]]
            else:
                license_plate_ += text[j]
        else:
            # Vị trí sau: giả định số, apply char_to_int
            if text[j] in dict_char_to_int:
                license_plate_ += dict_char_to_int[text[j]]
            else:
                license_plate_ += text[j]

    return license_plate_

def read_license_plate(license_plate_crop):
    """
    Read the license plate text from the given cropped image, handling multi-line for square plates.

    Args:
        license_plate_crop (PIL.Image.Image): Cropped image containing the license plate.

    Returns:
        tuple: Tuple containing the formatted license plate text and its confidence score.
    """

    detections = reader.readtext(license_plate_crop)

    if not detections:
        return None, None

    texts = []
    for detection in detections:
        bbox, text, score = detection
        text = text.upper().replace(' ', '').replace('-', '').replace('.', '')  # Loại bỏ dấu đặc biệt từ OCR
        # Lưu y-coordinate của top-left corner để sort theo dòng (từ trên xuống)
        y_top = bbox[0][1]
        texts.append((y_top, text, score))

    # Sort theo y (dòng trên trước)
    texts.sort(key=lambda x: x[0])

    # Ghép text từ các dòng
    combined_text = ''.join([t[1] for t in texts])

    # Tính score trung bình
    scores = [t[2] for t in texts if t[2] > 0]
    score = sum(scores) / len(scores) if scores else 0

    if license_complies_format(combined_text):
        return format_license(combined_text), score

    return None, None

def get_car(license_plate, vehicle_track_ids):
    """
    Retrieve the vehicle coordinates and ID based on the license plate coordinates.

    Args:
        license_plate (tuple): Tuple containing the coordinates of the license plate (x1, y1, x2, y2, score, class_id).
        vehicle_track_ids (list): List of vehicle track IDs and their corresponding coordinates.

    Returns:
        tuple: Tuple containing the vehicle coordinates (x1, y1, x2, y2) and ID.
    """
    x1, y1, x2, y2, score, class_id = license_plate

    foundIt = False
    for j in range(len(vehicle_track_ids)):
        xcar1, ycar1, xcar2, ycar2, car_id = vehicle_track_ids[j]

        if x1 > xcar1 and y1 > ycar1 and x2 < xcar2 and y2 < ycar2:
            car_indx = j
            foundIt = True
            break

    if foundIt:
        return vehicle_track_ids[car_indx]

    return -1, -1, -1, -1, -1