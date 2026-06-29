import pygame
from renderer import Renderer, ChallengeRenderer
from menu import MenuScreen
import random
from typing import Tuple, List
from maze import Maze, HuntAndKillGenerator, add_42_pattern, Cell
from path_finder import PathFinder

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

def _safe_random_cell(test_maze: Maze, w: int, h: int) -> Tuple[int, int]:
    """
    pick a random (x, y) inside the maze that is not on the 42
    pattern. Same approach used in menu.py / renderer.py — duplicated
    here in a small free function so Challenge Mode doesn't need to
    depend on MenuScreen or Renderer internals just for this.
    """
    while True:
        x = random.randint(0, w - 1)
        y = random.randint(0, h - 1)
        cell = test_maze.get_cell(x, y)
        if cell is not None and not cell.is_pattern:
            return x, y


def run_challenge_mode(screen: pygame.Surface, start_level: int) -> bool:
    """
    Run Challenge Mode (2-player race) starting at `start_level`.
    Each level builds a fresh maze sized per ChallengeRenderer.LEVEL_SIZES,
    picks one shared entry/exit pair (off the 42 pattern, never equal),
    solves it, and races both players on the identical maze/path.
    After level 3 is won, loops back to level 1 (endless replay) — the
    spec only defines 3 sizes, so wrapping keeps "next level" meaningful.

    Returns:
     True  - player chose to return to menu (ESC).
     False - window was closed.
    """
    level = start_level

    while True:
        width, height = ChallengeRenderer.LEVEL_SIZES.get(level, (40,40))

        maze = Maze(width, height)
        add_42_pattern(maze)
        HuntAndKillGenerator(random.randint(1, 10000)).generate(maze)

        entry = _safe_random_cell(maze, width, height)
        exit_pos = _safe_random_cell(maze, width, height)
        while exit_pos == entry:
            exit_pos = _safe_random_cell(maze, width, height)

        entry_cell = maze.get_cell(*entry)
        exit_cell = maze.get_cell(*exit_pos)
        path = PathFinder(maze).find_path(entry_cell, exit_cell)

        challenge = ChallengeRenderer(maze, entry, exit_pos, path,
                                      level, screen)
        outcome = challenge.run()

        if outcome is None:
            return False
        if outcome == "menu":
            return True
        if outcome == "next_level":
            level = level + 1 if level < 3 else 1
            continue


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