import cv2
import numpy as np
import math

def rotate_image(image: np.ndarray, angle: float) -> np.ndarray:
    """
    Xoay ảnh theo góc (đơn vị độ), giữ nguyên kích thước ảnh.
    """
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)

    rot_mat = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(image, rot_mat, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return rotated


def compute_skew(image: np.ndarray) -> float:
    """
    Tính góc nghiêng của biển số xe (âm là nghiêng trái, dương là nghiêng phải)
    """
    # Chuyển sang ảnh xám nếu cần
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # Làm mờ giảm nhiễu
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    # Canny edge detection
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    # Dò các đường thẳng bằng Hough Line Transform
    lines = cv2.HoughLines(edges, 1, np.pi / 180, 100)
    if lines is None:
        return 0.0

    angles = []
    for line in lines:
        rho, theta = line[0]
        angle = (theta * 180 / np.pi) - 90  # chuyển sang độ, xoay chuẩn về trục ngang
        if -45 < angle < 45:  # chỉ giữ góc hợp lý
            angles.append(angle)

    if len(angles) == 0:
        return 0.0

    # Lấy góc trung vị thay vì trung bình để loại bỏ nhiễu
    median_angle = np.median(angles)
    return median_angle


def deskew(image: np.ndarray) -> np.ndarray:
    """
    Hiệu chỉnh lại ảnh bị nghiêng, tự động tính góc nghiêng.
    """
    angle = compute_skew(image)
    if abs(angle) > 0.5:  # nếu nghiêng ít hơn 0.5°, bỏ qua
        rotated = rotate_image(image, -angle)
        return rotated
    return image


def enhance(image: np.ndarray) -> np.ndarray:
    """
    Tăng cường tương phản ảnh biển số trước khi xử lý.
    """
    # Nếu ảnh màu thì chuyển xám
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # Cải thiện tương phản bằng CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # Dùng top-hat và black-hat để nhấn mạnh biên ký tự
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    tophat = cv2.morphologyEx(enhanced, cv2.MORPH_TOPHAT, kernel)
    blackhat = cv2.morphologyEx(enhanced, cv2.MORPH_BLACKHAT, kernel)

    enhanced = cv2.add(enhanced, tophat)
    enhanced = cv2.subtract(enhanced, blackhat)
    return enhanced
