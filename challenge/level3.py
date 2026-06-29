
"""
NEW FILE (this iteration).

Level 3 — Tokyo Night: a chaser walks the solution path; if it
reaches the exit before either player, BOTH players lose.

ELI5: this level bolts on a single extra part — the chaser — using
the same hook pattern as level 2. The chaser walks the path at a
speed worked out from how long the path is, so every maze feels
about equally tense regardless of size.
"""

import pygame

from challenge.base import ChallengeRenderer


class Level3Renderer(ChallengeRenderer):
    """Chaser follows the solution path; reach the exit first to win."""

    LEVEL_NUMBER = 3
    LEVEL_NAME = "Tokyo Night"
    MAZE_SIZE = (40, 40)
    PALETTE_INDEX = 1   # "Tokyo Night" palette

    # target crossing time for the chaser, in milliseconds (~30 seconds,
    # but adjusted per path length so it's never absurdly fast/slow)
    TARGET_CROSSING_MS = 30_000
    MIN_STEP_DELAY_MS = 80

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Walks the solution path after reveal; reaches exit -> both lose.
        self.chaser_index = 0
        self.chaser_timer = 0
        path_len = max(1, len(self.path[0]))
        self.chaser_delay_ms = max(
            self.MIN_STEP_DELAY_MS, self.TARGET_CROSSING_MS // path_len)

    # ------------------------------------------------------------ hooks

    def _on_update(self, dt_ms: int) -> None:
        """Advance the chaser along the path; check if it reached exit."""
        if self.winner is not None:
            return

        self.chaser_timer += dt_ms
        while self.chaser_timer >= self.chaser_delay_ms:
            self.chaser_timer -= self.chaser_delay_ms
            if self.chaser_index < len(self.path[0]) - 1:
                self.chaser_index += 1
            if self.chaser_index >= len(self.path[0]) - 1:
                # chaser reached exit — both players lose
                self.winner = "Chaser"
                self.winner_time_ms = self.elapsed_ms
                break

    def _on_draw_extras(self) -> None:
        """Pulsing red dot that walks the solution path."""
        if self.chaser_index >= len(self.path[0]):
            return
        cell = self.path[0][self.chaser_index]
        cx, cy = self._cell_center(cell.x, cell.y)
        r = max(3, self.cell_length // 3)
        # pulse brightness over 600 ms cycle
        pulse = abs((self.elapsed_ms % 600) - 300) / 300.0
        bright = int(180 + 75 * pulse)
        pygame.draw.circle(self.canvas, (bright, 30, 30), (cx, cy), r)
        pygame.draw.circle(self.canvas, (255, 80, 80), (cx, cy), max(1, r // 2))

    def _on_panel_extras(self, x: int, y: int) -> int:
        """Chaser progress bar, only shown once the race has started."""
        if not self.reveal_done:
            return y
        pygame.draw.line(self.info_canvas, (80, 80, 100),
                          (x, y), (self.info_width - x, y), 1)
        y += 12
        pct = self.chaser_index / max(1, len(self.path[0]) - 1)
        bar_w = self.info_width - 2 * x
        pygame.draw.rect(self.info_canvas, (60, 30, 30),
                          (x, y, bar_w, 10))
        pygame.draw.rect(self.info_canvas, (220, 50, 50),
                          (x, y, int(bar_w * pct), 10))
        y += 14
        self.info_canvas.blit(
            self.font.render("Chaser progress", True, (220, 80, 80)),
            (x, y))
        y += 26
        return y
