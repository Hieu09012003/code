class Contour:
    def __init__(self, contour_data, numeric: bool = False):
        self.contour_data = contour_data
        self.is_numeric = numeric

    def get_contour(self) -> str:
        return self.contour_data

    def get_is_numeric(self) -> bool:
        return self.is_numeric

    @staticmethod
    def get_contours(contours_list: list) -> list:
        return [c.get_contour() for c in contours_list]

    @staticmethod
    def are_numerics(contours_list: list) -> list:
        return [c.is_numeric() for c in contours_list]

    def __str__(self) -> str:
        return f"Contour: {self.contour_data}, Numeric: {self.is_numeric}"