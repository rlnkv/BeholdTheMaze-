"""
Shared helpers for picking safe random cells in a maze.
"""

import random
from typing import Tuple

from maze import Maze


def is_on_pattern(maze: Maze, x: int, y: int) -> bool:
    """Return True if cell (x, y) is part of the blocked "42" pattern."""
    cell = maze.get_cell(x, y)
    return cell is not None and cell.is_pattern


def safe_random_cell(maze: Maze, width: int, height: int) -> Tuple[int, int]:
    """Pick a random (x, y) that is not on the 42 pattern."""
    while True:
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        if not is_on_pattern(maze, x, y):
            return x, y


def safe_random_entry_exit(
    maze: Maze, width: int, height: int
) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """Pick two distinct random cells, both off the 42 pattern."""
    entry = safe_random_cell(maze, width, height)
    exit_ = safe_random_cell(maze, width, height)
    while exit_ == entry:
        exit_ = safe_random_cell(maze, width, height)
    return entry, exit_
