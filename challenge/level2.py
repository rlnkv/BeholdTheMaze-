"""
NEW FILE (this iteration).

Level 2 — Synthwave Sunset: collectable triangles dropped every 12th
step along the solution path.

ELI5: this level bolts THREE extra parts onto the base chassis:
  1. a bag of collectables (self.collectables)
  2. a hook that drops a new collectable as the reveal-line passes it
  3. a hook that draws little triangles + a scoreboard
Everything else (movement, reveal animation, drawing walls, players)
is inherited from ChallengeRenderer for free.
"""

from typing import Set, Tuple

import pygame

from challenge.base import ChallengeRenderer


class Level2Renderer(ChallengeRenderer):
    """Collectables dropped every 12th step; race + collect."""

    LEVEL_NUMBER = 2
    LEVEL_NAME = "Synthwave"
    MAZE_SIZE = (30, 30)
    PALETTE_INDEX = 2   # "Synthwave Sunset" palette

    # every Nth path cell becomes a collectable triangle
    COLLECT_EVERY_N_STEPS = 12

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Every 12th path cell becomes a collectable triangle.
        # They are added progressively as the reveal line passes them.
        self.collectables: Set[Tuple[int, int]] = set()
        self.p1_collected = 0
        self.p2_collected = 0

    # ------------------------------------------------------------ hooks

    def _on_reveal_advanced(self, old_index: int, new_index: int) -> None:
        """Drop collectables as the head of the reveal line passes them."""
        for i, cell in enumerate(self.path[0]):
            if i > 0 and i % self.COLLECT_EVERY_N_STEPS == 0 and i <= new_index:
                self.collectables.add((cell.x, cell.y))

    def _on_collect(self) -> None:
        """Remove any collectables under either player, and score it."""
        if self.p1_pos in self.collectables:
            self.collectables.discard(self.p1_pos)
            self.p1_collected += 1
        if self.p2_pos in self.collectables:
            self.collectables.discard(self.p2_pos)
            self.p2_collected += 1

    def _on_draw_extras(self) -> None:
        """Small upward triangles at each collectable position."""
        r = max(3, self.cell_length // 5)
        for (cx, cy) in self.collectables:
            px, py = self._cell_center(cx, cy)
            tri = [(px, py - r), (px - r, py + r), (px + r, py + r)]
            pygame.draw.polygon(self.canvas, self.path_colour, tri)
            pygame.draw.polygon(self.canvas, (255, 255, 255), tri, 1)

    def _on_panel_extras(self, x: int, y: int) -> int:
        """Collectable scoreboard: P1 / P2 totals + remaining count."""
        pygame.draw.line(self.info_canvas, (80, 80, 100),
                          (x, y), (self.info_width - x, y), 1)
        y += 12
        self.info_canvas.blit(
            self.font.render(f"P1 collected: {self.p1_collected}",
                              True, self.p1_colour), (x, y))
        y += 24
        self.info_canvas.blit(
            self.font.render(f"P2 collected: {self.p2_collected}",
                              True, self.p2_colour), (x, y))
        y += 24
        self.info_canvas.blit(
            self.font.render(f"Remaining: {len(self.collectables)}",
                              True, self.text_colour), (x, y))
        y += 28
        return y