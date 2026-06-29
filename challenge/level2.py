"""
NEW FILE (this iteration).

Level 2 — Synthwave Sunset: collectable triangles dropped every 12th
step along the solution path.

ELI5: this level bolts THREE extra parts onto the base chassis:
  1. two bags of collectables, one per player colour
     (self.p1_collectables / self.p2_collectables)
  2. a hook that drops a new pair of triangles as the reveal-line
     passes each 12th cell
  3. a hook that draws the two little triangles + a scoreboard
Everything else (movement, reveal animation, drawing walls, players)
is inherited from ChallengeRenderer for free.

CHANGED (this iteration): each 12th cell now holds TWO triangles —
one in P1's colour, one in P2's colour — instead of a single shared
triangle either player could grab. Each player only ever removes
their OWN colour triangle when they step on the cell. So if P1 falls
behind, their violet triangle is still waiting for them even after
P2's gold triangle on that same cell has already been taken. ELI5:
think of it like two separate trails of breadcrumbs laid down at the
same spots — a violet trail for P1 and a gold trail for P2 — and
each player can only eat their own colour of breadcrumb.
"""

from typing import Set, Tuple

import pygame

from challenge.base import ChallengeRenderer


class Level2Renderer(ChallengeRenderer):
    """Two independent sets of collectables (one per player); race + collect."""

    LEVEL_NUMBER = 2
    LEVEL_NAME = "Synthwave"
    MAZE_SIZE = (30, 30)
    PALETTE_INDEX = 2   # "Synthwave Sunset" palette

    # every Nth path cell becomes a collectable triangle pair
    COLLECT_EVERY_N_STEPS = 12

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # NEW: two separate bags instead of one shared bag. Both start
        # with the same set of cell positions (every 12th path step),
        # but from then on each is only ever touched by its own player.
        self.p1_collectables: Set[Tuple[int, int]] = set()
        self.p2_collectables: Set[Tuple[int, int]] = set()
        self.p1_collected = 0
        self.p2_collected = 0

    # ------------------------------------------------------------ hooks

    def _on_reveal_advanced(self, old_index: int, new_index: int) -> None:
        """Drop a triangle PAIR (one per player) as the reveal line passes."""
        for i, cell in enumerate(self.path[0]):
            if i > 0 and i % self.COLLECT_EVERY_N_STEPS == 0 and i <= new_index:
                pos = (cell.x, cell.y)
                self.p1_collectables.add(pos)
                self.p2_collectables.add(pos)

    def _on_collect(self) -> None:
        """
        Each player only removes their OWN colour triangle.
        Stepping on a cell never affects the other player's triangle.
        """
        if self.p1_pos in self.p1_collectables:
            self.p1_collectables.discard(self.p1_pos)
            self.p1_collected += 1
        if self.p2_pos in self.p2_collectables:
            self.p2_collectables.discard(self.p2_pos)
            self.p2_collected += 1

    def _on_draw_extras(self) -> None:
        """
        Two small triangles per active cell — P1's colour on the left
        half, P2's colour on the right half of the cell, so both can
        sit side by side without overlapping.
        """
        r = max(3, self.cell_length // 6)
        offset = max(2, self.cell_length // 6)

        for (cx, cy) in self.p1_collectables:
            px, py = self._cell_center(cx, cy)
            px -= offset   # nudge left so it doesn't overlap P2's triangle
            tri = [(px, py - r), (px - r, py + r), (px + r, py + r)]
            pygame.draw.polygon(self.canvas, self.p1_colour, tri)
            pygame.draw.polygon(self.canvas, (255, 255, 255), tri, 1)

        for (cx, cy) in self.p2_collectables:
            px, py = self._cell_center(cx, cy)
            px += offset   # nudge right so it doesn't overlap P1's triangle
            tri = [(px, py - r), (px - r, py + r), (px + r, py + r)]
            pygame.draw.polygon(self.canvas, self.p2_colour, tri)
            pygame.draw.polygon(self.canvas, (255, 255, 255), tri, 1)

    def _on_panel_extras(self, x: int, y: int) -> int:
        """Collectable scoreboard: P1 / P2 totals + remaining-per-player count."""
        pygame.draw.line(self.info_canvas, (80, 80, 100),
                          (x, y), (self.info_width - x, y), 1)
        y += 12
        self.info_canvas.blit(
            self.font.render(
                f"P1 collected: {self.p1_collected}  "
                f"(left: {len(self.p1_collectables)})",
                True, self.p1_colour), (x, y))
        y += 24
        self.info_canvas.blit(
            self.font.render(
                f"P2 collected: {self.p2_collected}  "
                f"(left: {len(self.p2_collectables)})",
                True, self.p2_colour), (x, y))
        y += 28
        return y