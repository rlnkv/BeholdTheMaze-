"""
Level 3 — Tokyo Night.

A chaser walks the solution path. If it reaches the exit before both
players finish, everyone loses.
"""

import pygame

try:
    import game_sounds as sounds
except ImportError:
    class sounds:  # type: ignore
        @staticmethod
        def play(name: str) -> None: pass

from challenge.base import ChallengeRenderer


class Level3Renderer(ChallengeRenderer):
    """Race the chaser to the exit."""

    LEVEL_NUMBER  = 3
    LEVEL_NAME    = "Tokyo Night"
    MAZE_SIZE     = (40, 40)
    PALETTE_INDEX = 1

    TARGET_CROSSING_MS = 40_000
    MIN_STEP_DELAY_MS  = 80
    CHASER_TRACE_LEN   = 20

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.chaser_index = 0
        self.chaser_timer = 0
        path_len = max(1, len(self.path[0]))
        self.chaser_delay_ms = max(
            self.MIN_STEP_DELAY_MS, self.TARGET_CROSSING_MS // path_len)

    def _get_chaser_trace(self) -> list:
        start = max(0, self.chaser_index - self.CHASER_TRACE_LEN)
        return [(c.x, c.y) for c in self.path[0][start:self.chaser_index]]

    def _on_update(self, dt_ms: int) -> None:
        if self.winner is not None:
            return
        self.chaser_timer += dt_ms
        while self.chaser_timer >= self.chaser_delay_ms:
            self.chaser_timer -= self.chaser_delay_ms
            if self.chaser_index < len(self.path[0]) - 1:
                self.chaser_index += 1
                sounds.play("step_ch")
            if self.chaser_index >= len(self.path[0]) - 1:
                self.winner = "Chaser"
                self.winner_time_ms = self.elapsed_ms
                break

    def _on_draw_extras(self) -> None:
        self._draw_chaser(self.chaser_index, self._get_chaser_trace())

    def _on_panel_extras(self, x: int, y: int) -> int:
        if not self.reveal_done:
            return y
        pygame.draw.line(self.info_canvas, (80, 80, 100),
                         (x, y), (self.info_width - x, y), 1)
        y += 12
        pct   = self.chaser_index / max(1, len(self.path[0]) - 1)
        bar_w = self.info_width - 2 * x
        pygame.draw.rect(self.info_canvas, (60, 30, 30), (x, y, bar_w, 10))
        pygame.draw.rect(self.info_canvas, (220, 50, 50),
                         (x, y, int(bar_w * pct), 10))
        y += 14
        self.info_canvas.blit(
            self.font.render("Chaser progress", True, (220, 80, 80)), (x, y))
        return y + 26
