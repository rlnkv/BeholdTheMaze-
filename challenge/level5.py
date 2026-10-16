"""
Level 5 — Sync or Sink.

Sync stripes require both players to stay on the same cell. Break
sync for more than 1 second and both are teleported back to the
stripe entrance.
"""

import random
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

import pygame

try:
    import game_sounds as sounds
except ImportError:
    class sounds:  # type: ignore
        @staticmethod
        def init() -> None: pass
        @staticmethod
        def play(name: str) -> None: pass
from challenge.base import ChallengeRenderer


GRACE_MS = 1000   # ms allowed out-of-sync before teleport penalty


# ------------------------------------------------------------------ data

@dataclass
class SyncStripe:
    """One synchronisation corridor on the solution path."""
    cells:          List[Tuple[int, int]]
    cell_set:       Set[Tuple[int, int]]
    path_start_idx: int   = 0
    desync_ms:      float = 0.0


# ------------------------------------------------------------------ level

class Level5Renderer(ChallengeRenderer):
    """Sync-or-teleport corridors: both players must move together."""

    LEVEL_NUMBER  = 5
    LEVEL_NAME    = "Sync or Sink"
    MAZE_SIZE     = (35, 35)
    PALETTE_INDEX = 5        # Ember & Obsidian

    # stripe generation — same approach as level 4
    MIN_STRIPE_LEN  = 5
    MAX_STRIPE_LEN  = 10
    NUM_STRIPES_MIN = 2
    NUM_STRIPES_MAX = 3
    GAP_CELLS       = 2      # slightly larger gap: players need space to regroup
    PATH_MARGIN     = 6

    # visual
    STRIPE_FILL_ALPHA   = 110   # base fill brightness for each half of a cell
    STRIPE_BORDER_ALPHA = 200   # border brightness

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.stripes: List[SyncStripe] = self._build_stripes()
        self._cell_to_stripe: Dict[Tuple[int, int], SyncStripe] = {
            cell: stripe
            for stripe in self.stripes
            for cell in stripe.cells
        }
        self._flash_ms: float = 0.0
        self._flash_duration = 400.0

    # ---------------------------------------------------------------- stripe generation

    def _build_stripes(self) -> List[SyncStripe]:
        """Place non-overlapping, non-adjacent sync stripes along the path."""
        path_cells = self.path[0]
        n = len(path_cells)
        f_start = self.PATH_MARGIN
        f_end   = n - self.PATH_MARGIN

        if f_end - f_start < self.MIN_STRIPE_LEN * 2:
            return []

        rng = random.Random()
        num_stripes = rng.randint(self.NUM_STRIPES_MIN, self.NUM_STRIPES_MAX)
        occupied: Set[int] = set(range(0, f_start)) | set(range(f_end, n))
        stripes: List[SyncStripe] = []

        attempts = 0
        while len(stripes) < num_stripes and attempts < 200:
            attempts += 1
            length = rng.randint(self.MIN_STRIPE_LEN, self.MAX_STRIPE_LEN)
            start  = rng.randint(f_start, max(f_start, f_end - length))
            end    = start + length
            needed = set(range(start - self.GAP_CELLS, end + self.GAP_CELLS))
            if needed & occupied:
                continue
            cells = [(path_cells[i].x, path_cells[i].y) for i in range(start, end)]
            stripes.append(SyncStripe(cells=cells, cell_set=set(cells),
                                      path_start_idx=start))
            occupied |= needed

        cell_to_idx = {(c.x, c.y): i for i, c in enumerate(path_cells)}
        stripes.sort(key=lambda s: cell_to_idx[s.cells[0]])
        return stripes

    # ---------------------------------------------------------------- hooks

    def _on_update(self, dt_ms: int) -> None:
        """Accumulate desync time per stripe; teleport both players if grace expires."""
        if self.winner is not None:
            return
        if self._flash_ms > 0:
            self._flash_ms = max(0.0, self._flash_ms - dt_ms)

        for stripe in self.stripes:
            p1_in = self.p1_pos in stripe.cell_set
            p2_in = self.p2_pos in stripe.cell_set

            if not p1_in and not p2_in:
                stripe.desync_ms = 0.0
                continue
            if p1_in and p2_in and self.p1_pos == self.p2_pos:
                stripe.desync_ms = 0.0
                continue

            stripe.desync_ms += dt_ms
            if stripe.desync_ms >= GRACE_MS:
                self._teleport_to_stripe_start(stripe)

    def _teleport_to_stripe_start(self, stripe: SyncStripe) -> None:
        """Send both players to the first cell of the stripe together."""
        start = stripe.cells[0]
        self.p1_pos = start
        self.p2_pos = start
        self.p1_trace = []
        self.p2_trace = []
        stripe.desync_ms = 0.0
        self._flash_ms = self._flash_duration
        sounds.play("teleport")

    def _on_draw_extras(self) -> None:
        for stripe in self.stripes:
            p1_in   = self.p1_pos in stripe.cell_set
            p2_in   = self.p2_pos in stripe.cell_set
            active  = p1_in or p2_in
            in_sync = p1_in and p2_in and self.p1_pos == self.p2_pos
            frac    = min(1.0, stripe.desync_ms / GRACE_MS) if active else 0.0

            self._draw_stripe_ribbon(
                stripe.cells,
                stripe.path_start_idx,
                colour_a=self.p1_colour,
                colour_b=self.p2_colour,
                alpha=self.STRIPE_FILL_ALPHA,
                alpha_b=self.STRIPE_FILL_ALPHA,
            )

            if not stripe.cells:
                continue
            r = max(2, self.cell_length // 6)

            # Entry marker — two upward triangles (P1 left, P2 right)
            cx, cy = self._cell_center(*stripe.cells[0])
            self._draw_double_triangle(cx, cy, r, pointing_up=True)

            # Exit marker — two downward triangles
            cx, cy = self._cell_center(*stripe.cells[-1])
            self._draw_double_triangle(cx, cy, r, pointing_up=False)

            # Desync border
            if active and not in_sync:
                border_col = (
                    int(200 + 55 * frac),
                    int(200 * (1 - frac)),
                    int(200 * (1 - frac)),
                )
                border_w = max(1, int(1 + frac * 2))
                for cx, cy in stripe.cells:
                    x0, y0 = self._cell_top_left(cx, cy)
                    pygame.draw.rect(
                        self.canvas, border_col,
                        (x0, y0, self.cell_length, self.cell_length),
                        border_w)

        if self._flash_ms > 0:
            alpha = int(180 * (self._flash_ms / self._flash_duration))
            flash = pygame.Surface((self.maze_area_width, self.maze_area_height))
            flash.fill((255, 255, 255))
            flash.set_alpha(alpha)
            self.canvas.blit(flash, (0, 0))

    def _on_panel_extras(self, x: int, y: int) -> int:
        """
        For each stripe: show a grace-timer bar that fills red as
        players fall out of sync, labelled with the stripe number.
        """
        pygame.draw.line(self.info_canvas, (80, 80, 100),
                          (x, y), (self.info_width - x, y), 1)
        y += 12

        bar_w = self.info_width - 2 * x

        for i, stripe in enumerate(self.stripes):
            p1_in = self.p1_pos in stripe.cell_set
            p2_in = self.p2_pos in stripe.cell_set
            active = p1_in or p2_in
            frac   = min(1.0, stripe.desync_ms / GRACE_MS) if active else 0.0

            # stripe label
            self.info_canvas.blit(
                self.font.render(f"Sync zone {i + 1}", True,
                                  self.text_colour), (x, y))
            y += 18

            # background trough
            pygame.draw.rect(self.info_canvas, (50, 30, 30),
                              (x, y, bar_w, 8))

            # filled portion: green when fine, red when danger
            if frac > 0:
                fill_colour = (
                    int(50 + 170 * frac),      # R: grows to red
                    int(200 * (1 - frac)),      # G: shrinks
                    50,
                )
                pygame.draw.rect(self.info_canvas, fill_colour,
                                  (x, y, int(bar_w * frac), 8))

            y += 12

            # "teleport!" warning text when almost out of time
            if active and frac > 0.75:
                self.info_canvas.blit(
                    self.font.render("Teleport incoming!",
                                      True, (255, 80, 80)), (x, y))
                y += 20
            else:
                y += 4

        return y + 6
