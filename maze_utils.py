"""
NEW FILE (this iteration).

This file holds small helper functions about the MAZE itself
(picking safe random cells, checking the 42 pattern) that used to be
copy-pasted in menu.py, renderer.py (twice!) and a_maze_ing.py.

ELI5: think of this like a shared toolbox. Instead of every room in
the house (every file) buying its own hammer, everyone borrows the
one hammer from this toolbox.
"""

import random
from typing import Tuple

from maze import Maze


def is_on_pattern(maze: Maze, x: int, y: int) -> bool:
    """
    Return True if cell (x, y) is part of the "42" pattern (blocked).

    Used to reject entry/exit points placed on the pattern.
    """
    cell = maze.get_cell(x, y)
    return cell is not None and cell.is_pattern


def safe_random_cell(maze: Maze, width: int, height: int) -> Tuple[int, int]:
    """
    Pick a random (x, y) inside the maze that is NOT on the 42 pattern.

    Keeps re-rolling until it lands on a free cell. This never loops
    forever in practice because the pattern only blocks a small
    handful of cells out of the whole maze.

    This one function replaces the THREE near-identical copies that
    used to live in menu.py, renderer.py, and a_maze_ing.py.
    """
    while True:
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        if not is_on_pattern(maze, x, y):
            return x, y


def safe_random_entry_exit(
    maze: Maze, width: int, height: int
) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """
    Pick a random entry AND exit, off the pattern, guaranteed different.

    This is the "pick entry, then pick exit, re-roll if they match"
    dance that showed up at every call site that needed both points.
    """
    entry = safe_random_cell(maze, width, height)
    exit_ = safe_random_cell(maze, width, height)
    while exit_ == entry:
        exit_ = safe_random_cell(maze, width, height)
    return entry, exit_
