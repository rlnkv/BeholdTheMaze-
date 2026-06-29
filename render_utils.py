"""
NEW FILE (this iteration).

This file holds small helper functions about DRAWING (fonts, wall
pixels, geometry math) that used to be copy-pasted between the
Renderer class and the ChallengeRenderer class in renderer.py.

ELI5: Renderer and ChallengeRenderer both need to know "how big is
one cell in pixels" and "how do I draw one wall side". Instead of
each one having its own copy of that math, they both call these
shared functions now.
"""

import os
from typing import Tuple

import pygame

# the two places we look for a nicer font before falling back to the
# pygame default. Same list that used to be re-typed in 3 different
# __init__ methods.
_FONT_CANDIDATES_RELATIVE = [
    "DejaVuSans.ttf",
    os.path.join("dejavu-sans", "DejaVuSans.ttf"),
]


def load_font(size: int, here: str) -> pygame.font.Font:
    """
    Load DejaVuSans at the given size, or fall back to pygame's
    built-in font if the .ttf file isn't found.

    `here` is the directory of the calling file (pass
    os.path.dirname(os.path.abspath(__file__))) so this keeps working
    no matter which file calls it.
    """
    for relative_path in _FONT_CANDIDATES_RELATIVE:
        full_path = os.path.join(here, relative_path)
        if os.path.isfile(full_path):
            return pygame.font.Font(full_path, size)
    return pygame.font.SysFont(None, size)


def recalculate_geometry(
    maze_area_width: int,
    maze_area_height: int,
    maze_width: int,
    maze_height: int,
    min_padding: int,
) -> Tuple[int, int, int, int]:
    """
    Work out the pixel sizing for drawing a maze of (maze_width x
    maze_height) cells inside an area of (maze_area_width x
    maze_area_height) pixels.

    Returns (cell_length, stroke_length, padding_x, padding_y).

    This is the exact math that used to live twice: once in
    Renderer._recalculate_geometry and once in
    ChallengeRenderer._recalculate_geometry.
    """
    available_w = maze_area_width - 2 * min_padding
    available_h = maze_area_height - 2 * min_padding

    step_w = (available_w * 9) // (9 * maze_width + 1)
    step_h = (available_h * 9) // (9 * maze_height + 1)
    step = min(step_w, step_h)

    stroke_length = max(1, step // 3)
    cell_length = step + stroke_length

    real_width = maze_width * step + stroke_length
    real_height = maze_height * step + stroke_length
    padding_x = (maze_area_width - real_width) // 2
    padding_y = (maze_area_height - real_height) // 2

    return cell_length, stroke_length, padding_x, padding_y


def draw_side_of_cell(
    surface: pygame.Surface,
    colour: Tuple[int, int, int],
    direction: str,
    x0: int,
    y0: int,
    cell_length: int,
    stroke_length: int,
) -> None:
    """
    Draw one wall segment (or corner) of a cell.

    direction is one of: N, NE, E, SE, S, SW, W, NW.

    This is the same rectangle math that used to be duplicated as
    Renderer._draw_side_of_cell and ChallengeRenderer._draw_side_of_cell.
    """
    s, cl = stroke_length, cell_length
    rects = {
        "N":  (x0 + s,      y0,           cl - 2 * s, s),
        "NE": (x0 + cl - s, y0,           s,          s),
        "E":  (x0 + cl - s, y0 + s,       s,          cl - 2 * s),
        "SE": (x0 + cl - s, y0 + cl - s,  s,          s),
        "S":  (x0 + s,      y0 + cl - s,  cl - 2 * s, s),
        "SW": (x0,          y0 + cl - s,  s,          s),
        "W":  (x0,          y0 + s,       s,          cl - 2 * s),
        "NW": (x0,          y0,           s,          s),
    }
    if direction in rects:
        pygame.draw.rect(surface, colour, rects[direction])


def cell_top_left(
    x: int, y: int, cell_length: int, stroke_length: int,
    padding_x: int, padding_y: int,
) -> Tuple[int, int]:
    """Pixel coordinates of the top-left corner of maze cell (x, y)."""
    step = cell_length - stroke_length
    return (x * step + padding_x, y * step + padding_y)


def cell_center(
    x: int, y: int, cell_length: int, stroke_length: int,
    padding_x: int, padding_y: int,
) -> Tuple[int, int]:
    """Pixel coordinates of the center of maze cell (x, y)."""
    step = cell_length - stroke_length
    return (
        x * step + padding_x + cell_length // 2,
        y * step + padding_y + cell_length // 2,
    )


def dim_colour(colour: Tuple[int, int, int], alpha: int) -> Tuple[int, int, int]:
    """
    Darken a colour by alpha (255 = full brightness, 0 = black).
    No pygame.Surface alpha-blending needed, just simple math.
    """
    a = alpha / 255.0
    return (int(colour[0] * a), int(colour[1] * a), int(colour[2] * a))