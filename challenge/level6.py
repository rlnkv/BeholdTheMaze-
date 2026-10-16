"""
Level 6 — The Gauntlet.

Combines owned stripes (level 4), sync stripes (level 5), and a slow
chaser (level 3). Both players must finish before the chaser arrives.
"""

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

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


GRACE_MS = 1000


@dataclass
class MixedStripe:
    """
    One stripe — either "owned" (one-colored, level 4 rules) or
    "sync" (two-colored, level 5 rules).
    """
    cells:            List[Tuple[int, int]]
    cell_set:         Set[Tuple[int, int]]
    kind:             str            # "owned" | "sync"
    owner:            str   = "p1"
    path_start_idx:   int   = 0
    cell_before:      Optional[Tuple[int, int]] = None  # intruder teleport target
    p1_was_in:        bool  = False
    p2_was_in:        bool  = False
    p1_was_on_exit:   bool  = False
    p2_was_on_exit:   bool  = False
    p1_intruder_ms:   float = 0.0
    p2_intruder_ms:   float = 0.0
    desync_ms:        float = 0.0


class Level6Renderer(ChallengeRenderer):
    """Owned stripes + sync stripes + slow chaser. Both must finish first."""

    LEVEL_NUMBER  = 6
    LEVEL_NAME    = "The Gauntlet"
    MAZE_SIZE     = (35, 35)
    PALETTE_INDEX = 6

    MIN_STRIPE_LEN  = 5
    MAX_STRIPE_LEN  = 10
    NUM_STRIPES_MIN = 4
    NUM_STRIPES_MAX = 5
    GAP_CELLS       = 2
    PATH_MARGIN     = 6

    TARGET_CROSSING_MS = 100_000
    MIN_STEP_DELAY_MS  = 100
    CHASER_TRACE_LEN   = 20

    OWNED_ALPHA         = 140
    OWNED_ALPHA_BLOCKED = 80
    SYNC_FILL_ALPHA     = 110

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.stripes: List[MixedStripe] = self._build_stripes()
        self._cell_to_stripe: Dict[Tuple[int, int], MixedStripe] = {
            cell: stripe
            for stripe in self.stripes
            for cell in stripe.cells
        }
        self.chaser_index = 0
        self.chaser_timer = 0
        path_len = max(1, len(self.path[0]))
        self.chaser_delay_ms = max(
            self.MIN_STEP_DELAY_MS,
            self.TARGET_CROSSING_MS // path_len)
        self._flash_ms: float = 0.0
        self._flash_duration: float = 400.0

    # ---------------------------------------------------------------- stripe generation

    def _build_stripes(self) -> List[MixedStripe]:
        """Place 4–5 mixed owned/sync stripes, guaranteeing at least one of each."""
        path_cells = self.path[0]
        n = len(path_cells)
        f_start = self.PATH_MARGIN
        f_end   = n - self.PATH_MARGIN

        if f_end - f_start < self.MIN_STRIPE_LEN * 2:
            return []

        rng = random.Random()
        num_stripes = rng.randint(self.NUM_STRIPES_MIN, self.NUM_STRIPES_MAX)
        occupied: Set[int] = set(range(0, f_start)) | set(range(f_end, n))
        raw: List[Tuple[int, int]] = []

        attempts = 0
        while len(raw) < num_stripes and attempts < 400:
            attempts += 1
            length = rng.randint(self.MIN_STRIPE_LEN, self.MAX_STRIPE_LEN)
            start  = rng.randint(f_start, max(f_start, f_end - length))
            end    = start + length
            needed = set(range(start - self.GAP_CELLS, end + self.GAP_CELLS))
            if needed & occupied:
                continue
            raw.append((start, end))
            occupied |= needed

        raw.sort()

        kinds = ["owned" if rng.random() >= 0.5 else "sync" for _ in raw]
        if "owned" not in kinds:
            kinds[rng.randint(0, len(kinds) - 1)] = "owned"
        if "sync" not in kinds:
            kinds[rng.randint(0, len(kinds) - 1)] = "sync"

        stripes = []
        for (start, end), kind in zip(raw, kinds):
            cells = [(path_cells[i].x, path_cells[i].y) for i in range(start, end)]
            cell_before = (path_cells[start - 1].x, path_cells[start - 1].y) \
                          if start > 0 else (path_cells[0].x, path_cells[0].y)
            stripes.append(MixedStripe(
                cells=cells, cell_set=set(cells),
                kind=kind, owner=rng.choice(["p1", "p2"]),
                path_start_idx=start,
                cell_before=cell_before,
            ))
        return stripes

    def _is_move_blocked(self, player: str, target_pos: Tuple[int, int]) -> bool:
        # Owned stripes no longer hard-block — intruder timer handles eviction.
        return False

    def _on_collect(self) -> None:
        """Flip owned-stripe ownership on exit-cell departure; reset sync timer on reunite."""
        for stripe in self.stripes:
            p1_in = self.p1_pos in stripe.cell_set
            p2_in = self.p2_pos in stripe.cell_set
            if stripe.kind == "owned":
                exit_cell      = stripe.cells[-1]
                p1_on_exit_now = self.p1_pos == exit_cell
                p2_on_exit_now = self.p2_pos == exit_cell
                if stripe.owner == "p1" and stripe.p1_was_on_exit and not p1_in:
                    stripe.owner = "p2"
                    stripe.p2_intruder_ms = 0.0
                    sounds.play("handoff")
                elif stripe.owner == "p2" and stripe.p2_was_on_exit and not p2_in:
                    stripe.owner = "p1"
                    stripe.p1_intruder_ms = 0.0
                    sounds.play("handoff")
                stripe.p1_was_in      = p1_in
                stripe.p2_was_in      = p2_in
                stripe.p1_was_on_exit = p1_on_exit_now
                stripe.p2_was_on_exit = p2_on_exit_now
            else:
                if p1_in and p2_in and self.p1_pos == self.p2_pos:
                    stripe.desync_ms = 0.0

    def _on_update(self, dt_ms: int) -> None:
        """Advance desync timers, intruder timers, and the chaser each frame."""
        if self.winner is not None:
            return

        self._flash_ms = max(0.0, self._flash_ms - dt_ms)

        for stripe in self.stripes:
            p1_in = self.p1_pos in stripe.cell_set
            p2_in = self.p2_pos in stripe.cell_set

            if stripe.kind == "owned":
                # non-owner intruder timer
                if stripe.owner == "p1":
                    if p2_in:
                        stripe.p2_intruder_ms += dt_ms
                        if stripe.p2_intruder_ms >= GRACE_MS:
                            self.p2_pos = stripe.cell_before
                            self.p2_trace = []
                            stripe.p2_intruder_ms = 0.0
                            sounds.play("teleport")
                    else:
                        stripe.p2_intruder_ms = 0.0
                else:
                    if p1_in:
                        stripe.p1_intruder_ms += dt_ms
                        if stripe.p1_intruder_ms >= GRACE_MS:
                            self.p1_pos = stripe.cell_before
                            self.p1_trace = []
                            stripe.p1_intruder_ms = 0.0
                            sounds.play("teleport")
                    else:
                        stripe.p1_intruder_ms = 0.0
            else:
                # sync stripe desync timer
                if not p1_in and not p2_in:
                    stripe.desync_ms = 0.0
                elif p1_in and p2_in and self.p1_pos == self.p2_pos:
                    stripe.desync_ms = 0.0
                else:
                    stripe.desync_ms += dt_ms
                    if stripe.desync_ms >= GRACE_MS:
                        self._teleport(stripe)
                        sounds.play("teleport")

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

    def _teleport(self, stripe: MixedStripe) -> None:
        """Send both players to stripe start together (sync penalty)."""
        start = stripe.cells[0]
        self.p1_pos = start
        self.p2_pos = start
        self.p1_trace = []
        self.p2_trace = []
        stripe.desync_ms = 0.0
        self._flash_ms = self._flash_duration

    # ---------------------------------------------------------------- drawing

    def _get_chaser_trace(self) -> List[Tuple[int, int]]:
        start = max(0, self.chaser_index - self.CHASER_TRACE_LEN)
        return [(c.x, c.y) for c in self.path[0][start:self.chaser_index]]

    def _on_draw_extras(self) -> None:
        s = self.stroke_length
        for stripe in self.stripes:
            if stripe.kind == "owned":
                self._draw_owned_stripe(stripe, s)
            else:
                self._draw_sync_stripe(stripe, s)

        self._draw_chaser(self.chaser_index, self._get_chaser_trace())

        if self._flash_ms > 0:
            alpha = int(180 * (self._flash_ms / self._flash_duration))
            flash = pygame.Surface((self.maze_area_width, self.maze_area_height))
            flash.fill((255, 255, 255))
            flash.set_alpha(alpha)
            self.canvas.blit(flash, (0, 0))

    def _draw_owned_stripe(self, stripe: MixedStripe, s: int) -> None:
        col = self.p1_colour if stripe.owner == "p1" else self.p2_colour
        self._draw_stripe_ribbon(
            stripe.cells, stripe.path_start_idx,
            colour_a=col, alpha=self.OWNED_ALPHA,
        )
        if not stripe.cells:
            return
        r = max(2, self.cell_length // 5)

        # Entry marker — upward triangle on first cell
        px, py = self._cell_center(*stripe.cells[0])
        tri_up = [(px, py - r), (px - r, py + r), (px + r, py + r)]
        pygame.draw.polygon(self.canvas, col, tri_up)
        pygame.draw.polygon(self.canvas, (255, 255, 255), tri_up, 1)

        # Exit marker — downward triangle on last cell
        px, py = self._cell_center(*stripe.cells[-1])
        tri_down = [(px, py + r), (px - r, py - r), (px + r, py - r)]
        pygame.draw.polygon(self.canvas, col, tri_down)
        pygame.draw.polygon(self.canvas, (255, 255, 255), tri_down, 1)

        # Intruder warning border
        intruder_frac = 0.0
        if stripe.owner == "p1" and self.p2_pos in stripe.cell_set:
            intruder_frac = min(1.0, stripe.p2_intruder_ms / GRACE_MS)
        elif stripe.owner == "p2" and self.p1_pos in stripe.cell_set:
            intruder_frac = min(1.0, stripe.p1_intruder_ms / GRACE_MS)
        if intruder_frac > 0:
            warn_col = (int(220 * intruder_frac), 0, 0)
            for cx, cy in stripe.cells:
                x0, y0 = self._cell_top_left(cx, cy)
                pygame.draw.rect(self.canvas, warn_col,
                                 (x0, y0, self.cell_length, self.cell_length), 2)

    def _draw_sync_stripe(self, stripe: MixedStripe, s: int) -> None:
        p1_in   = self.p1_pos in stripe.cell_set
        p2_in   = self.p2_pos in stripe.cell_set
        active  = p1_in or p2_in
        in_sync = p1_in and p2_in and self.p1_pos == self.p2_pos
        frac    = min(1.0, stripe.desync_ms / GRACE_MS) if active else 0.0

        self._draw_stripe_ribbon(
            stripe.cells, stripe.path_start_idx,
            colour_a=self.p1_colour, colour_b=self.p2_colour,
            alpha=self.SYNC_FILL_ALPHA, alpha_b=self.SYNC_FILL_ALPHA,
        )

        if stripe.cells:
            r = max(2, self.cell_length // 6)
            cx, cy = self._cell_center(*stripe.cells[0])
            self._draw_double_triangle(cx, cy, r, pointing_up=True)
            cx, cy = self._cell_center(*stripe.cells[-1])
            self._draw_double_triangle(cx, cy, r, pointing_up=False)

        if active and not in_sync:
            border_col = (int(200 + 55*frac), int(200*(1-frac)), int(100*(1-frac)))
            border_w   = max(1, int(1 + frac * 2))
            for cx, cy in stripe.cells:
                x0, y0 = self._cell_top_left(cx, cy)
                pygame.draw.rect(self.canvas, border_col,
                                 (x0, y0, self.cell_length, self.cell_length),
                                 border_w)

    def _on_panel_extras(self, x: int, y: int) -> int:
        """
        Chaser progress bar, then per-stripe type indicators
        (ownership dot for owned; desync bar for sync).
        """
        pygame.draw.line(self.info_canvas, (80, 80, 100),
                          (x, y), (self.info_width - x, y), 1)
        y += 10

        # chaser bar
        pct   = self.chaser_index / max(1, len(self.path[0]) - 1)
        bar_w = self.info_width - 2 * x
        pygame.draw.rect(self.info_canvas, (60, 30, 30), (x, y, bar_w, 10))
        pygame.draw.rect(self.info_canvas, (220, 50, 50),
                          (x, y, int(bar_w * pct), 10))
        y += 14
        self.info_canvas.blit(
            self.font.render("Chaser", True, (220, 80, 80)), (x, y))
        y += 22

        pygame.draw.line(self.info_canvas, (80, 80, 100),
                          (x, y), (self.info_width - x, y), 1)
        y += 10

        for i, stripe in enumerate(self.stripes):
            label = f"Zone {i + 1}"

            if stripe.kind == "owned":
                col   = self.p1_colour if stripe.owner == "p1" else self.p2_colour
                owner = "P1" if stripe.owner == "p1" else "P2"
                pygame.draw.circle(self.info_canvas, col, (x + 8, y + 9), 7)
                self.info_canvas.blit(
                    self.font.render(f"{label}: {owner}'s turn",
                                      True, self.text_colour), (x + 22, y))
                y += 22

            else:  # sync
                p1_in  = self.p1_pos in stripe.cell_set
                p2_in  = self.p2_pos in stripe.cell_set
                active = p1_in or p2_in
                frac   = min(1.0, stripe.desync_ms / GRACE_MS) if active else 0.0
                self.info_canvas.blit(
                    self.font.render(f"{label}: sync",
                                      True, self.text_colour), (x, y))
                y += 18
                pygame.draw.rect(self.info_canvas, (50, 30, 30),
                                  (x, y, bar_w, 7))
                if frac > 0:
                    fill_col = (int(50 + 170 * frac), int(200 * (1 - frac)), 50)
                    pygame.draw.rect(self.info_canvas, fill_col,
                                      (x, y, int(bar_w * frac), 7))
                y += 10
                if active and frac > 0.75:
                    self.info_canvas.blit(
                        self.font.render("Teleport!", True, (255, 80, 80)),
                        (x, y))
                    y += 18
                else:
                    y += 4

        return y + 4
