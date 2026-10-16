"""
BFS pathfinder for the maze.
"""

import collections
from typing import Dict, List, Optional, Set, Tuple

from maze import Cell, Maze, DIRECTIONS


class PathFinder:
    """Finds the shortest path between two cells using breadth-first search."""

    def __init__(self, maze: Maze) -> None:
        self.maze = maze

    def find_path(
        self, start: Optional[Cell], end: Optional[Cell]
    ) -> Tuple[List[Cell], List[str]]:
        """
        Return (cells, directions) for the shortest path from start to end.
        Both lists are empty if no path exists or either argument is None.
        """
        if not start or not end:
            return [], []

        parents: Dict[Cell, Optional[Tuple[str, Cell]]] = {start: None}
        queue: collections.deque[Cell] = collections.deque([start])

        while queue:
            current = queue.popleft()
            if current is end:
                break
            for direction, neighbor in self._open_neighbors(current):
                if neighbor not in parents:
                    parents[neighbor] = (direction, current)
                    queue.append(neighbor)

        if end not in parents:
            return [], []

        # Reconstruct path by walking back from end to start.
        path: List[Cell] = []
        directions: List[str] = []
        node: Optional[Cell] = end
        while node is not None:
            path.append(node)
            info = parents[node]
            if info is None:
                break
            direction, node = info
            directions.append(direction)

        path.reverse()
        directions.reverse()
        return path, directions

    def _open_neighbors(self, cell: Cell) -> List[Tuple[str, Cell]]:
        """Return (direction, neighbor) pairs for walls that have been removed."""
        result = []
        for direction, (dx, dy) in DIRECTIONS.items():
            if not cell.walls[direction]:
                neighbor = self.maze.get_cell(cell.x + dx, cell.y + dy)
                if neighbor is not None:
                    result.append((direction, neighbor))
        return result
