"""
Entry point — starts pygame, shows the menu, and runs the chosen mode.
"""

import random
from typing import List, Tuple

import pygame

from challenge.runner import run_challenge_mode
from maze import Cell, HuntAndKillGenerator, Maze, add_42_pattern
from menu import MenuScreen
from path_finder import PathFinder
from renderer import Renderer


class MazeGenerator:
    """Generates and solves a maze with the given parameters."""

    def __init__(
        self,
        width: int,
        height: int,
        entry: Tuple[int, int],
        exit: Tuple[int, int],
        seed: int | None,
    ) -> None:
        self.width  = width
        self.height = height
        self.entry  = entry
        self.exit   = exit
        self.seed   = seed if seed is not None else random.randint(1, 10000)
        self.maze: Maze

    def generate(self) -> Maze:
        """Build and return the maze."""
        self.maze = Maze(self.width, self.height)
        add_42_pattern(self.maze)
        HuntAndKillGenerator(self.seed).generate(self.maze)
        return self.maze

    def solve(self) -> Tuple[List[Cell], List[str]]:
        """Return the (cells, directions) solution path."""
        entry_cell = self.maze.get_cell(*self.entry)
        exit_cell  = self.maze.get_cell(*self.exit)
        return PathFinder(self.maze).find_path(entry_cell, exit_cell)


def main() -> None:
    pygame.init()
    import game_sounds as sounds
    sounds.init()
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption("Behold! The MAZE!")

    try:
        while True:
            result = MenuScreen(screen).run()

            if result is None:
                break

            if result[0] == "challenge":
                _, level = result
                if not run_challenge_mode(screen, level):
                    break
                continue

            width, height, entry, exit_pos, seed, is_random = result
            gen  = MazeGenerator(width, height, entry, exit_pos, seed)
            maze = gen.generate()
            path = gen.solve()

            if not Renderer(maze, path, entry, exit_pos, screen,
                            randomize_on_regen=is_random).run():
                break

    except KeyboardInterrupt:
        pass
    except Exception:
        pygame.quit()
        raise
    pygame.quit()


if __name__ == "__main__":
    main()
