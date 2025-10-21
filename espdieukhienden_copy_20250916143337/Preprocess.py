import numpy as np
import cv2

def gray_scale(image: np.ndarray):
    if len(image.shape) == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

def enchance_contrast(image: np.ndarray, kernel_size: int = 3):
    # using top hat and black hat
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    top_hat = cv2.morphologyEx(image, cv2.MORPH_TOPHAT, kernel)
    black_hat = cv2.morphologyEx(image, cv2.MORPH_BLACKHAT, kernel)
    image = cv2.add(image, top_hat)
    image = cv2.subtract(image, black_hat)
    return image

# TODO: implement this function
def thresholding(image: np.ndarray):
    pass

def morp_open(image: np.ndarray, kernel_size: int = 3):
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    return cv2.morphologyEx(image, cv2.MORPH_OPEN, kernel)

def morp_close(image: np.ndarray, kernel_size: int = 3):
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    return cv2.morphologyEx(image, cv2.MORPH_CLOSE, kernel)