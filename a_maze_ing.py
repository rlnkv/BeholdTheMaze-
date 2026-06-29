import pygame
from renderer import Renderer
from menu import MenuScreen
from challenge.runner import run_challenge_mode  # NEW: moved out of this file, see challenge/runner.py
import random
from typing import Tuple, List
from maze import Maze, HuntAndKillGenerator, add_42_pattern, Cell
from path_finder import PathFinder

# NOTE: _safe_random_cell and run_challenge_mode used to live in this
# file. _safe_random_cell is now the shared maze_utils.safe_random_cell
# (no longer needed directly here at all), and run_challenge_mode moved
# to challenge/runner.py so all challenge-mode code lives in one place.


class MazeGenerator:
    """
    Generate and solve mazes using configurable parameters.

    Attributes:
        width (int): Width of the maze.
        height (int): Height of the maze.
        entry (Tuple[int, int]): Entry coordinates.
        exit (Tuple[int, int]): Exit coordinates.
        seed (int): Random seed used for generation.
        maze (Maze): Generated maze instance.
    """

    def __init__(self, width: int, height: int,
                 entry: Tuple[int, int],
                 exit: Tuple[int, int],
                 seed: int | None) -> None:
        self.width = width
        self.height = height
        self.entry = entry
        self.exit = exit
        self.seed = seed if seed is not None else random.randint(1, 10000)

    def generate(self) -> Maze:
        """
        Generate and return a maze instance.

        Initializes a maze, applies a predefined 42 pattern,
        and runs the hunt-and-kill generation algorithm.

        Returns:
            Maze: Generated maze instance.
        """
        self.maze = Maze(self.width, self.height)
        add_42_pattern(self.maze)
        generator = HuntAndKillGenerator(self.seed)
        generator.generate(self.maze)
        return self.maze

    def solve(self) -> Tuple[List[Cell], List[str]]:
        """
        Solve the maze and return the path.

        Uses a pathfinding algorithm to compute a path from the
        entry cell to the exit cell.

        Returns:
            Tuple[List[Cell], List[str]]: Path as a list of cells
                and corresponding directions.
        """
        pathfinder = PathFinder(self.maze)
        entry_cell = self.maze.get_cell(*self.entry)
        exit_cell = self.maze.get_cell(*self.exit)
        path = pathfinder.find_path(entry_cell, exit_cell)
        return path


def main() -> None:
    """
    Program entry point.

    1. Start pygame and open the window once — shared by all screens.
    2. Show the menu and let the user pick settings.
    3. Generate the maze with those settings.
    4. Hand everything to the Renderer.
    """
    pygame.init()
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption("Behold! The MAZE!")

    try:
        while True:
            menu = MenuScreen(screen)
            result = menu.run()

            if result is None:
                break

            if result[0] == "challenge":
                _, level = result
                back_to_menu = run_challenge_mode(screen, level)
                if not back_to_menu:
                    break
                continue

            width, height, entry, exit_pos, seed, is_random = result

            generator = MazeGenerator(width, height, entry,
                                      exit_pos, seed)
            maze = generator.generate()
            path = generator.solve()

            renderer = Renderer(maze, path, entry, exit_pos, screen,
                                randomize_on_regen=is_random)
            back_to_menu = renderer.run()
            if not back_to_menu:
                break

    except KeyboardInterrupt:
        pass   # Ctrl-C is a normal way to quit; no traceback needed
    except Exception as e:
        pygame.quit()
        raise   # re-raise so the traceback is visible in the terminal
    pygame.quit()


if __name__ == "__main__":
    main()