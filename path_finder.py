from typing import List, Tuple, Set, Dict
from maze import Maze, Cell


class PathFinder:
    """
    Finds a path in a maze using BFS search.

    Implements breadth-first search to explore reachable cells and
    reconstruct a path from start to end.

    Attributes:
    queue (List[Cell]): BFS exploration queue.
    visited (Set[Cell]): Set of visited cells.
    parents (Dict[Cell, Tuple[str, Cell] | None]): Mapping of
    each cell to its parent and direction.
    maze (Maze): Maze instance being processed.
    """
    def __init__(self, maze: Maze):
        """Initialize the path finder with a maze."""
        self.maze = maze
        self.queue: List[Cell] = []
        self.visited: Set[Cell] = set()
        self.parents: Dict[Cell, Tuple[str, Cell] | None] = {}

    def _get_neighbors(self, cell: Cell) -> List[Tuple[str, Cell | None]]:
        """
        Get accessible neighboring cells from the current cell.

        Args:
        cell (Cell): Current cell.

        Returns:
        List[Tuple[str, Cell | None]]: Direction and neighbor pairs.
        """
        result = []
        for direction in cell.walls:
            if cell.walls[direction] is False:
                if direction == "N":
                    neighbor_x = cell.x
                    neighbor_y = cell.y - 1
                if direction == "E":
                    neighbor_x = cell.x + 1
                    neighbor_y = cell.y
                if direction == "S":
                    neighbor_x = cell.x
                    neighbor_y = cell.y + 1
                if direction == "W":
                    neighbor_x = cell.x - 1
                    neighbor_y = cell.y
                if (neighbor_x >= 0 and neighbor_x < self.maze.width and
                   neighbor_y >= 0 and neighbor_y < self.maze.height):
                    result.append((direction, self.maze.get_cell(neighbor_x,
                                                                 neighbor_y)))
        return result

    def _bfs(self, start: Cell, end: Cell) -> None:
        """
        Perform Breadth-first search to explore the maze.

        Args:
        start (Cell): Start cell.
        end (Cell): End cell.
        """
        self.queue = [start]
        self.visited = {start}
        self.parents = {start: None}

        while self.queue:
            current = self.queue.pop(0)

            if (current.x == end.x
               and current.y == end.y):
                break

            for direction, neighbor in self._get_neighbors(current):
                if neighbor is None:
                    continue
                if neighbor not in self.visited:
                    self.visited.add(neighbor)
                    self.parents[neighbor] = (direction, current)
                    self.queue.append(neighbor)

    def find_path(self, start: Cell | None,
                  end: Cell | None) -> Tuple[List[Cell], List[str]]:
        """
        Find a path from start to end in the maze.

        Args:
        start (Cell | None): Start cell.
        end (Cell | None): End cell.

        Returns:
        Tuple[List[Cell], List[str]]: Path and directions.
        """
        if not start or not end:
            return ([], [])

        self._bfs(start, end)

        if end not in self.parents:
            return ([], [])

        path = []
        directions = []
        current = end

        while current is not None:
            path.append(current)
            parent_info = self.parents[current]
            if parent_info is None:
                break
            direction, parent = parent_info
            directions.append(direction)
            current = parent

        path.reverse()
        directions.reverse()
        return path, directions