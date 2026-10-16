"""
Shared drawing helpers: font loading, geometry math, wall segments.
"""

import os
from typing import Tuple

import pygame


_FONT_CANDIDATES = [
    "DejaVuSans.ttf",
    os.path.join("dejavu-sans", "DejaVuSans.ttf"),
]


def load_font(size: int, here: str) -> pygame.font.Font:
    """
    Load DejaVuSans at `size` points from the directory `here`,
    falling back to pygame's built-in font if the file is not found.
    """
    for name in _FONT_CANDIDATES:
        path = os.path.join(here, name)
        if os.path.isfile(path):
            return pygame.font.Font(path, size)
    return pygame.font.SysFont(None, size)


def recalculate_geometry(
    area_width: int,
    area_height: int,
    maze_width: int,
    maze_height: int,
    min_padding: int,
) -> Tuple[int, int, int, int]:
    """
    Compute pixel dimensions for drawing a maze inside an area.
    Returns (cell_length, stroke_length, padding_x, padding_y).
    """
    available_w = area_width  - 2 * min_padding
    available_h = area_height - 2 * min_padding

    step = min(
        (available_w * 9) // (9 * maze_width  + 1),
        (available_h * 9) // (9 * maze_height + 1),
    )
    stroke = max(1, step // 3)
    cell   = step + stroke

    padding_x = (area_width  - (maze_width  * step + stroke)) // 2
    padding_y = (area_height - (maze_height * step + stroke)) // 2

    return cell, stroke, padding_x, padding_y


def draw_side_of_cell(
    surface: pygame.Surface,
    colour: Tuple[int, int, int],
    direction: str,
    x0: int, y0: int,
    cell_length: int,
    stroke_length: int,
) -> None:
    """Draw one wall segment or corner of a cell. direction ∈ {N,NE,E,SE,S,SW,W,NW}."""
    s, cl = stroke_length, cell_length
    rects = {
        "N":  (x0 + s,      y0,           cl - 2*s, s),
        "NE": (x0 + cl - s, y0,           s,        s),
        "E":  (x0 + cl - s, y0 + s,       s,        cl - 2*s),
        "SE": (x0 + cl - s, y0 + cl - s,  s,        s),
        "S":  (x0 + s,      y0 + cl - s,  cl - 2*s, s),
        "SW": (x0,          y0 + cl - s,  s,        s),
        "W":  (x0,          y0 + s,       s,        cl - 2*s),
        "NW": (x0,          y0,           s,        s),
    }
    if direction in rects:
        pygame.draw.rect(surface, colour, rects[direction])


def cell_top_left(
    x: int, y: int,
    cell_length: int, stroke_length: int,
    padding_x: int, padding_y: int,
) -> Tuple[int, int]:
    """Pixel coordinates of the top-left corner of maze cell (x, y)."""
    step = cell_length - stroke_length
    return x * step + padding_x, y * step + padding_y


def cell_center(
    x: int, y: int,
    cell_length: int, stroke_length: int,
    padding_x: int, padding_y: int,
) -> Tuple[int, int]:
    """Pixel coordinates of the centre of maze cell (x, y)."""
    step = cell_length - stroke_length
    return (
        x * step + padding_x + cell_length // 2,
        y * step + padding_y + cell_length // 2,
    )


def dim_colour(colour: Tuple[int, int, int], alpha: int) -> Tuple[int, int, int]:
    """Darken a colour by alpha (255 = full brightness, 0 = black)."""
    a = alpha / 255.0
    return int(colour[0] * a), int(colour[1] * a), int(colour[2] * a)
