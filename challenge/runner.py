"""
NEW FILE (this iteration).

This is the "race director". It picks which level class to use,
builds a fresh maze sized for that level, and runs the race loop.
It used to be a function called run_challenge_mode() sitting inside
a_maze_ing.py — moved here so all challenge-mode code lives together
under the challenge/ folder.

ELI5: this is like the tournament organizer. It doesn't play the
race itself (that's challenge/base.py and the level files) — it just
sets up the right maze for the right level, hands it to the right
level class, and decides what happens next (next level? back to
menu? quit?).
"""

import random

import pygame

from maze import Maze, HuntAndKillGenerator, add_42_pattern
from maze_utils import safe_random_entry_exit
from path_finder import PathFinder
from renderer import PALETTES
from challenge.level1 import Level1Renderer
from challenge.level2 import Level2Renderer
from challenge.level3 import Level3Renderer
from challenge.level4 import Level4Renderer
from challenge.level5 import Level5Renderer
from challenge.level6 import Level6Renderer

# level number -> the Renderer class that handles it.
# To add more levels: write challenge/levelN.py, then add it here.
LEVEL_RENDERERS = {
    1: Level1Renderer,
    2: Level2Renderer,
    3: Level3Renderer,
    4: Level4Renderer,
    5: Level5Renderer,
    6: Level6Renderer,
}


PATH_MIN = 40
PATH_MAX = 80


def _build_maze_with_valid_path(renderer_class):
    """
    Generate a maze and entry/exit pair whose solution path is between
    PATH_MIN and PATH_MAX steps long.  Re-rolls the seed and entry/exit
    until the constraint is satisfied — this converges quickly for any
    maze that is at least 20x20.
    """
    width, height = renderer_class.MAZE_SIZE
    while True:
        maze = Maze(width, height)
        add_42_pattern(maze)
        HuntAndKillGenerator(random.randint(1, 10000)).generate(maze)
        entry, exit_pos = safe_random_entry_exit(maze, width, height)
        path = PathFinder(maze).find_path(
            maze.get_cell(*entry), maze.get_cell(*exit_pos))
        if PATH_MIN <= len(path[0]) <= PATH_MAX:
            return maze, entry, exit_pos, path


def run_challenge_mode(screen: pygame.Surface, start_level: int) -> bool:
    """
    Run Challenge Mode starting at `start_level`.
    After the last level is won, loops back to level 1.

    Returns True if the player chose to return to menu, False if the
    window was closed.
    """
    level = start_level
    last_level = max(LEVEL_RENDERERS)

    while True:
        renderer_class = LEVEL_RENDERERS.get(level, Level1Renderer)
        maze, entry, exit_pos, path = _build_maze_with_valid_path(renderer_class)

        challenge = renderer_class(maze, entry, exit_pos, path, screen, PALETTES)
        outcome = challenge.run()

        if outcome is None:
            return False
        if outcome == "menu":
            return True
        if outcome == "next_level":
            level = level + 1 if level < last_level else 1
            continue