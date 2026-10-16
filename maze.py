"""
Core maze data structures and the Hunt-and-Kill generation algorithm.
"""

import random
from typing import List, Optional, Tuple


# Direction vectors: name -> (dx, dy)
DIRECTIONS: dict[str, Tuple[int, int]] = {
    "N": (0, -1),
    "E": (1,  0),
    "S": (0,  1),
    "W": (-1, 0),
}

# When we remove a wall between two cells we must remove it on both sides.
OPPOSITE: dict[str, str] = {"N": "S", "E": "W", "S": "N", "W": "E"}


class Cell:
    """One cell in the maze grid."""

    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y
        self.visited: bool = False
        self.is_pattern: bool = False
        # All four walls start closed; generation removes them selectively.
        self.walls = {"N": True, "E": True, "S": True, "W": True}


class Maze:
    """Rectangular grid of Cell objects."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.grid: List[List[Cell]] = [
            [Cell(x, y) for x in range(width)]
            for y in range(height)
        ]

    def get_cell(self, x: int, y: int) -> Optional[Cell]:
        """Return the cell at (x, y), or None if out of bounds."""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.grid[y][x]
        return None

    def neighbors(self, cell: Cell) -> List[Tuple[str, "Cell"]]:
        """Return (direction, neighbor) pairs for all in-bounds, non-pattern neighbors."""
        result = []
        for direction, (dx, dy) in DIRECTIONS.items():
            neighbor = self.get_cell(cell.x + dx, cell.y + dy)
            if neighbor is not None and not neighbor.is_pattern:
                result.append((direction, neighbor))
        return result

    def remove_wall(self, c1: Cell, c2: Cell, direction: str) -> None:
        """Remove the wall between c1 and c2 (updates both sides)."""
        c1.walls[direction] = False
        c2.walls[OPPOSITE[direction]] = False


class HuntAndKillGenerator:
    """
    Generates a perfect maze using the Hunt-and-Kill algorithm.

    Uses a private random.Random instance so generating one maze never
    affects random state anywhere else in the program.  Passing the same
    seed always produces the same maze; omitting it gives a fresh random one.
    """

    def __init__(self, seed: Optional[int] = None) -> None:
        self._rng = random.Random(seed)

    def generate(self, maze: Maze) -> None:
        """Carve passages through the maze in-place."""
        current = maze.get_cell(0, 0)
        if current is None:
            return
        current.visited = True

        while current:
            unvisited = [
                (d, n) for d, n in maze.neighbors(current) if not n.visited
            ]
            if unvisited:
                self._rng.shuffle(unvisited)
                current = self._kill(maze, current, unvisited)
            else:
                current = self._hunt(maze)

    def _kill(
        self, maze: Maze, current: Cell,
        candidates: List[Tuple[str, Cell]],
    ) -> Cell:
        """
        Walk phase: try each unvisited neighbor and move to the first
        one that won't create an open room.  If all would create a room,
        fall through to hunt.
        """
        for direction, next_cell in candidates:
            if not self._creates_large_room(maze, current, direction):
                maze.remove_wall(current, next_cell, direction)
                next_cell.visited = True
                return next_cell
        return self._hunt(maze)

    def _hunt(self, maze: Maze) -> Optional[Cell]:
        """
        Hunt phase: scan the grid for an unvisited cell that has at
        least one visited neighbor, then connect them.
        """
        candidates = []
        for y in range(maze.height):
            for x in range(maze.width):
                cell = maze.get_cell(x, y)
                if cell is None or cell.visited or cell.is_pattern:
                    continue
                visited_neighbors = [
                    (d, n) for d, n in maze.neighbors(cell) if n.visited
                ]
                if visited_neighbors:
                    candidates.append((cell, visited_neighbors))

        if not candidates:
            return None

        cell, visited_neighbors = self._rng.choice(candidates)
        direction, neighbor = self._rng.choice(visited_neighbors)
        maze.remove_wall(cell, neighbor, direction)
        cell.visited = True
        return cell

    def _creates_large_room(self, maze: Maze, cell: Cell, direction: str) -> bool:
        """
        Return True if removing the wall in this direction would leave any
        cell in the 3x3 neighbourhood around the target with 3+ open walls
        (which would create an unwanted open room).
        """
        dx, dy = DIRECTIONS[direction]
        nx, ny = cell.x + dx, cell.y + dy
        for y in range(ny - 1, ny + 2):
            for x in range(nx - 1, nx + 2):
                c = maze.get_cell(x, y)
                if c is not None and sum(not w for w in c.walls.values()) >= 3:
                    return True
        return False


def add_42_pattern(maze: Maze) -> None:
    """
    Mark a "42" glyph in the centre of the maze as impassable pattern cells.
    Requires at least a 9x7 maze.
    """
    if maze.width < 9 or maze.height < 7:
        print("Maze is too small for the 42 pattern — needs at least 9x7.")
        return

    cx = maze.width // 2
    cy = maze.height // 2

    # Relative (dx, dy) offsets for the "4" and "2" glyphs.
    glyph_4 = [(0, 0), (0, 1), (0, 2), (1, 2), (2, 2), (2, 3), (2, 4)]
    glyph_2 = [
        (0, 0), (1, 0), (2, 0),
        (2, 1),
        (0, 2), (1, 2), (2, 2),
        (0, 3),
        (0, 4), (1, 4), (2, 4),
    ]

    origin_4 = (cx - 3, cy - 2)
    origin_2 = (cx + 1, cy - 2)

    def block(x: int, y: int) -> None:
        cell = maze.get_cell(x, y)
        if cell is None:
            return
        cell.is_pattern = True
        cell.visited = True
        cell.walls = {"N": True, "E": True, "S": True, "W": True}
        # Close the touching wall on every adjacent cell too.
        for direction, (dx, dy) in DIRECTIONS.items():
            neighbor = maze.get_cell(x + dx, y + dy)
            if neighbor:
                neighbor.walls[OPPOSITE[direction]] = True

    for dx, dy in glyph_4:
        block(origin_4[0] + dx, origin_4[1] + dy)
    for dx, dy in glyph_2:
        block(origin_2[0] + dx, origin_2[1] + dy)


def render_maze(maze: Maze) -> None:
    """Print an ASCII representation of the maze (used for testing)."""
    print("+" + "---+" * maze.width)
    for y in range(maze.height):
        row = "|"
        bottom = "+"
        for x in range(maze.width):
            cell = maze.get_cell(x, y)
            if cell is None:
                continue
            row += "███" if cell.is_pattern else "   "
            row += "|" if cell.walls["E"] else " "
            bottom += "---+" if cell.walls["S"] else "   +"
        print(row)
        print(bottom)
