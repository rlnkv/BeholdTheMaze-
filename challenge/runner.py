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

# level number -> the Renderer class that handles it.
# To add a level 4, write challenge/level4.py with a Level4Renderer
# subclass, then add it here. Nothing else in this file needs to change.
LEVEL_RENDERERS = {
    1: Level1Renderer,
    2: Level2Renderer,
    3: Level3Renderer,
}


def run_challenge_mode(screen: pygame.Surface, start_level: int) -> bool:
    """
    Run Challenge Mode (2-player race) starting at `start_level`.

    Each level builds a fresh maze sized per that level's MAZE_SIZE,
    picks one shared entry/exit pair (off the 42 pattern, never
    equal), solves it, and races both players on the identical
    maze/path. After the last level is won, loops back to level 1
    (endless replay).

    Returns:
        True  - player chose to return to menu (ESC).
        False - window was closed.
    """
    level = start_level
    last_level = max(LEVEL_RENDERERS)

    while True:
        renderer_class = LEVEL_RENDERERS.get(level, Level1Renderer)
        width, height = renderer_class.MAZE_SIZE

        maze = Maze(width, height)
        add_42_pattern(maze)
        HuntAndKillGenerator(random.randint(1, 10000)).generate(maze)

        entry, exit_pos = safe_random_entry_exit(maze, width, height)

        entry_cell = maze.get_cell(*entry)
        exit_cell = maze.get_cell(*exit_pos)
        path = PathFinder(maze).find_path(entry_cell, exit_cell)

        challenge = renderer_class(maze, entry, exit_pos, path,
                                    screen, PALETTES)
        outcome = challenge.run()

        if outcome is None:
            return False
        if outcome == "menu":
            return True
        if outcome == "next_level":
            level = level + 1 if level < last_level else 1
            continue