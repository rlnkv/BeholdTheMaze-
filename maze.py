import random
from typing import List, Tuple, Optional

"""
Naming the direction where we are moving from current cell.
Also really importand while deleting walls between cells
"""
DIRECTIONS: dict[str, Tuple[int, int]] = {
    "N": (0, -1),
    "E": (1, 0),
    "S": (0, 1),
    "W": (-1, 0),
}

"""
EACH cell have walls, during wall deletion,
so when we move from cell1 to cell2,
we need to delete in cell1 wall in the direction of moving,
and in cell2 we need to delete the wall in opposite direction.
"""
OPPOSITE: dict[str, str] = {
    "N": "S",
    "E": "W",
    "S": "N",
    "W": "E",
}

""""
Creating class Cell.
Attributes - the coordinates of a cell
Each cell have walls and atributes -
was it visited bu kill phase or it is the part of a pattern.
Also each cell is "born" blocked.
"""


class Cell:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y
        self.visited: bool = False
        self.walls = {"N": True, "E": True, "S": True, "W": True}

        self.is_pattern: bool = False


"""
Creating class Maze with attributes width and height.
It has grid - coordinates of cells in the maze.
"""


class Maze:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.grid: List[List[Cell]] = [
            [Cell(x, y) for x in range(width)]
            for y in range(height)
        ]

    """ getting the cell with coordinates """
    def get_cell(self, x: int, y: int) -> Optional[Cell]:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.grid[y][x]
        return None

    """ This method creates list of neighboring cells of the current cell."""
    def neighbors(self, cell: Cell) -> List[Tuple[str, Cell]]:
        result: List[Tuple[str, Cell]] = []

        for direction, (dx, dy) in DIRECTIONS.items():
            nx, ny = cell.x + dx, cell.y + dy
            neighbor = self.get_cell(nx, ny)

            if neighbor is not None and not neighbor.is_pattern:
                result.append((direction, neighbor))
        return result

    """ when "moving", we remove wall in cell1
    and touching wall in neighboring cell2
    """
    def remove_wall(self, c1: Cell, c2: Cell, direction: str) -> None:
        c1.walls[direction] = False
        c2.walls[OPPOSITE[direction]] = False


"""
Creating class HuntAndKillGenerator, that generates maze.
it's the main engine in this program.
As an optional argument it has seed
same seed - same maze every time, random seed - random maze
"""


class HuntAndKillGenerator:
    """
    Uses its own private random.Random instance (self._rng) instead of
    the global random.seed(). That matters because the menu's
    background maze always uses a fixed seed (42); if that reseeded
    the shared/global random module, it would silently make the NEXT
    "random" pick anywhere else in the program (e.g. "pick a random
    seed for the next challenge maze") deterministic too — which is
    why mazes used to repeat. Each generator now keeps its own
    separate shuffle-machine, so generating one maze never affects
    randomness anywhere else.

    same seed - same maze every time, random seed - random maze.
    """

    def __init__(self, seed: Optional[int] = None) -> None:
        self._rng = random.Random(seed)

    """ Generate method - has an maze (parameters of maze) as an attribute.
    We start at the left upper corner and start randomly move through maze,
    removing walls between cells, marking each visited cell,
    and each time randomly chosing unvisited neigbor to move further.
    if we stuck, amd there's no aviluble cells (every neighbor is visited,
    or it is pattern, or moving that way creates open "room"),
    we start "hunt" phase.
    """
    def generate(self, maze: Maze) -> None:

        current = maze.get_cell(0, 0)
        if current is None:
            return

        current.visited = True

        while current:
            # killing phase
            unvisited_neighbors = [
                (d, n)
                for d, n in maze.neighbors(current)
                if not n.visited
            ]

            if unvisited_neighbors:
                self._rng.shuffle(unvisited_neighbors)

                moved = False

                for direction, next_cell in unvisited_neighbors:
                    if not self._creates_large_room(maze, current, direction):
                        maze. remove_wall(current, next_cell, direction)
                        next_cell.visited = True
                        current = next_cell
                        moved = True
                        break

                if not moved:
                    current = self._hunt(maze)
            else:
                current = self._hunt(maze)

    """
    Hunt - is the phase, where we find unvisited cell with visited neighbor,
    We find them and append them to the list of candidates to kill (append
    to visited neighbor), then randomly chose between
    candidates and append them,
    if it will not create open "room". Then moves till it could not.
    Then hunt begins allover.
    As an attribute is the maze (must hunt inside maze coordinates),
    as an output we give visited cell ( if there is any left).
    """
    def _hunt(self, maze: Maze) -> Optional[Cell]:
        candidates = []
        for y in range(maze.height):
            for x in range(maze.width):
                cell = maze.get_cell(x, y)
                if cell is None or cell.visited or cell.is_pattern:
                    continue

                visited_neighbors = [
                    (d, n)
                    for d, n in maze.neighbors(cell)
                    if n.visited
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

    """
    This method checks if the neighboring cells (all 8)
    have 3 already removed walls.
    If they are, removing 4-th wall would create a "room" - noone wants that.
    As an attributes this method has  maze, cell and directon -
    to check cells in all directions from current one.
    """
    def _creates_large_room(
            self,
            maze: Maze,
            cell: Cell,
            direction: str
    ) -> bool:
        dx, dy = DIRECTIONS[direction]
        nx, ny = cell.x + dx, cell.y + dy

        """ checking small square around target"""
        for y in range(ny - 1, ny + 2):
            for x in range(nx - 1, nx + 2):
                c = maze.get_cell(x, y)
                if c is None:
                    continue
                # Counting open walls
                open_walls = sum(not w for w in c.walls.values())
                if open_walls >= 3:
                    return True
        return False


"""
Pattern:
+---+           +---+---+---+
|   |           |   |   |   |
+---+           +---+---+---+
|   |                   |   |
+---+---+---+   +---+---+---+
|   |   |   |   |   |   |   |
+---+---+---+   +---+---+---+
        |   |   |   |
        +---+   +---+---+---+
        |   |   |   |   |   |
        +---+   +---+---+---+

We create pattern in the center of the maze.
So as an attribute we need only maze.
To fit properly and still have room for the maze, we need at least 9x7 maze.

"""


def add_42_pattern(maze: Maze) -> None:
    """ check if fits"""
    if maze.width < 9 or maze.height < 7:
        print("Maze is too small for 42! \n Be more Ambitious.")
        return

    """ finding center of maze"""
    center_x = maze.width // 2
    center_y = maze.height // 2

    """ defining relative 42 coordinates"""
    pattern_4 = [
        (0, 0), (0, 1), (0, 2),
        (1, 2),
        (2, 2), (2, 3), (2, 4)
    ]
    pattern_2 = [
        (0, 0), (1, 0), (2, 0),
        (2, 1),
        (0, 2), (1, 2), (2, 2),
        (0, 3),
        (0, 4), (1, 4), (2, 4),
    ]

    """ defining where 4 and 2 should be relative to the center"""
    offset_4_x = center_x - 3
    offset_4_y = center_y - 2

    offset_2_x = center_x + 1
    offset_2_y = center_y - 2

    """ For pattern we use fully closed (blocked) cells.
    as an attributes we need coordinates of each cell."""
    def block_cell(x: int, y: int) -> None:
        cell = maze.get_cell(x, y)
        if cell is None:
            return

        """ Marking cell as a pattern part
        marking it as visited, to hide it from _hunt"""
        cell.is_pattern = True
        cell.visited = True

        """ using fully closed cells for pattern"""
        cell.walls = {"N": True, "E": True, "S": True, "W": True}

        """
        we need to "close" the walls of the cells,
        that touch the pattern
        """
        for direction, (dx, dy) in DIRECTIONS.items():
            neighbor = maze.get_cell(x + dx, y + dy)
            if neighbor:
                neighbor.walls[OPPOSITE[direction]] = True

    """creating pattern. 4 and 2 apart,
    so it would be easy to generate maze between them."""
    for dx, dy in pattern_4:
        block_cell(offset_4_x + dx, offset_4_y + dy)

    for dx, dy in pattern_2:
        block_cell(offset_2_x + dx, offset_2_y + dy)



"""
This function "draws" the maze in ASCII symbols.
We need this to proerly test it
"""


def render_maze(maze: Maze) -> None:
    width = maze.width
    height = maze.height

    """ drawing borders - top"""
    print("+" + "---+" * width)

    """Vertical and horizontl lines"""
    for y in range(height):
        line1 = "|"
        line2 = "+"

        for x in range(width):
            cell = maze.get_cell(x, y)
            if cell is None:
                continue
            """ this is used to mark pattern cells"""
            if cell.is_pattern:
                line1 += "███"
            else:
                """ space in all other cells"""
                line1 += "   "

            """ "Drawing" right wall"""
            if cell.walls["E"]:
                line1 += "|"
            else:
                line1 += " "

            """ bottom wall"""
            if cell.walls["S"]:
                line2 += "---+"
            else:
                line2 += "   +"

        print(line1)
        print(line2)


"""
This function used to test rendering maze.
"""


def get_user_input() -> tuple[int, int, Optional[int]]:
    try:
        width = int(input("give me width, pls: "))
        height = int(input("And also height: "))

        seed_input = input("Last thing - seed. Enter seed number: ")
        seed = int(seed_input) if seed_input else None

        if width <= 0 or height <= 0:
            raise ValueError

        return width, height, seed
    except ValueError:
        print("bad numbers, my master.\n But I'll give you 10x10 maze")
        return 10, 10, None


def main() -> None:
    print("=== HUNT and KILL ===")
    width, height, seed = get_user_input()

    maze = Maze(width, height)

    add_42_pattern(maze)

    generator = HuntAndKillGenerator(seed)

    generator.generate(maze)

    print("\n Behold! The MAZE: \n")
    render_maze(maze)


if __name__ == "__main__":
    main()