"""
Level 4 — Neon Divide.

The solution path contains 2–3 "owned" stripes painted in the
owner's colour.  Rules:

  * The OWNER can walk through the stripe freely.
  * The NON-OWNER can also enter, but if they stay inside for more
    than 1 second they are teleported to the cell immediately before
    the stripe entrance.
  * Ownership transfers when the owner steps OUT past the EXIT cell
    (the last cell of the stripe).  The exit cell is marked with a
    downward triangle.
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


INTRUDER_GRACE_MS = 1000   # ms a non-owner may stay inside before teleport


@dataclass
class Stripe:
    """One owned corridor along the solution path."""
    cells:              List[Tuple[int, int]]
    cell_set:           Set[Tuple[int, int]]
    owner:              str            # "p1" or "p2"
    path_start_idx:     int  = 0
    cell_before:        Optional[Tuple[int, int]] = None
    p1_was_in:          bool  = False
    p2_was_in:          bool  = False
    # handoff only fires when owner leaves from the exit cell specifically
    p1_was_on_exit:     bool  = False
    p2_was_on_exit:     bool  = False
    p1_intruder_ms:     float = 0.0
    p2_intruder_ms:     float = 0.0


class Level4Renderer(ChallengeRenderer):
    """Owned-stripe race: both players must finish to win."""

    LEVEL_NUMBER  = 4
    LEVEL_NAME    = "Neon Divide"
    MAZE_SIZE     = (35, 35)
    PALETTE_INDEX = 4

    MIN_STRIPE_LEN  = 5
    MAX_STRIPE_LEN  = 10
    NUM_STRIPES_MIN = 2
    NUM_STRIPES_MAX = 3
    GAP_CELLS       = 1
    PATH_MARGIN     = 6

    STRIPE_ALPHA = 140

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.stripes: List[Stripe] = self._build_stripes()
        self._cell_to_stripe: Dict[Tuple[int, int], Stripe] = {
            cell: stripe
            for stripe in self.stripes
            for cell in stripe.cells
        }

    def _build_stripes(self) -> List[Stripe]:
        """Place non-overlapping owned stripes along the path."""
        path_cells = self.path[0]
        n          = len(path_cells)
        f_start    = self.PATH_MARGIN
        f_end      = n - self.PATH_MARGIN

        if f_end - f_start < self.MIN_STRIPE_LEN * 2:
            return []

        rng         = random.Random()
        num_stripes = rng.randint(self.NUM_STRIPES_MIN, self.NUM_STRIPES_MAX)
        occupied: Set[int] = set(range(0, f_start)) | set(range(f_end, n))
        stripes: List[Stripe] = []

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

            # cell immediately before the stripe — teleport target for intruders
            cell_before = (path_cells[start - 1].x, path_cells[start - 1].y) \
                          if start > 0 else (path_cells[0].x, path_cells[0].y)

            stripes.append(Stripe(
                cells=cells,
                cell_set=set(cells),
                owner=rng.choice(["p1", "p2"]),
                path_start_idx=start,
                cell_before=cell_before,
            ))
            occupied |= needed

        cell_to_idx = {(c.x, c.y): i for i, c in enumerate(path_cells)}
        stripes.sort(key=lambda s: cell_to_idx[s.cells[0]])
        return stripes

    # ---------------------------------------------------------------- hooks

    def _is_move_blocked(self, player: str, target_pos: Tuple[int, int]) -> bool:
        # Non-owners can now enter; the intruder timer handles the penalty.
        return False

    def _on_collect(self) -> None:
        """
        Transfer ownership only when the owner steps OFF the exit cell.
        Leaving from the middle of the stripe (retreating) does NOT hand off.
        """
        for stripe in self.stripes:
            exit_cell = stripe.cells[-1]
            p1_in          = self.p1_pos in stripe.cell_set
            p2_in          = self.p2_pos in stripe.cell_set
            p1_on_exit_now = self.p1_pos == exit_cell
            p2_on_exit_now = self.p2_pos == exit_cell

            if stripe.owner == "p1":
                if stripe.p1_was_on_exit and not p1_in:
                    stripe.owner = "p2"
                    stripe.p2_intruder_ms = 0.0
                    sounds.play("handoff")
            else:
                if stripe.p2_was_on_exit and not p2_in:
                    stripe.owner = "p1"
                    stripe.p1_intruder_ms = 0.0
                    sounds.play("handoff")

            stripe.p1_was_in      = p1_in
            stripe.p2_was_in      = p2_in
            stripe.p1_was_on_exit = p1_on_exit_now
            stripe.p2_was_on_exit = p2_on_exit_now

    def _on_update(self, dt_ms: int) -> None:
        """Accumulate intruder time and teleport non-owners who overstay."""
        if self.winner is not None:
            return

        for stripe in self.stripes:
            p1_in = self.p1_pos in stripe.cell_set
            p2_in = self.p2_pos in stripe.cell_set

            if stripe.owner == "p1":
                # P2 is the potential intruder
                if p2_in:
                    stripe.p2_intruder_ms += dt_ms
                    if stripe.p2_intruder_ms >= INTRUDER_GRACE_MS:
                        self.p2_pos = stripe.cell_before
                        self.p2_trace = []
                        stripe.p2_intruder_ms = 0.0
                        sounds.play("teleport")
                else:
                    stripe.p2_intruder_ms = 0.0
            else:
                # P1 is the potential intruder
                if p1_in:
                    stripe.p1_intruder_ms += dt_ms
                    if stripe.p1_intruder_ms >= INTRUDER_GRACE_MS:
                        self.p1_pos = stripe.cell_before
                        self.p1_trace = []
                        stripe.p1_intruder_ms = 0.0
                        sounds.play("teleport")
                else:
                    stripe.p1_intruder_ms = 0.0

    # ---------------------------------------------------------------- drawing

    def _on_draw_extras(self) -> None:
        for stripe in self.stripes:
            col = self.p1_colour if stripe.owner == "p1" else self.p2_colour
            self._draw_stripe_ribbon(
                stripe.cells,
                stripe.path_start_idx,
                colour_a=col,
                alpha=self.STRIPE_ALPHA,
            )

        for stripe in self.stripes:
            if not stripe.cells:
                continue
            col = self.p1_colour if stripe.owner == "p1" else self.p2_colour

            # Entry marker — upward triangle on first cell
            px, py = self._cell_center(*stripe.cells[0])
            r = max(2, self.cell_length // 5)
            tri_up = [(px, py - r), (px - r, py + r), (px + r, py + r)]
            pygame.draw.polygon(self.canvas, col, tri_up)
            pygame.draw.polygon(self.canvas, (255, 255, 255), tri_up, 1)

            # Exit marker — downward triangle on last cell
            px, py = self._cell_center(*stripe.cells[-1])
            tri_down = [(px, py + r), (px - r, py - r), (px + r, py - r)]
            pygame.draw.polygon(self.canvas, col, tri_down)
            pygame.draw.polygon(self.canvas, (255, 255, 255), tri_down, 1)

            # Intruder warning: dim red tint over cells when non-owner is inside
            stripe_set = stripe.cell_set
            intruder_frac = 0.0
            if stripe.owner == "p1" and self.p2_pos in stripe_set:
                intruder_frac = min(1.0, stripe.p2_intruder_ms / INTRUDER_GRACE_MS)
            elif stripe.owner == "p2" and self.p1_pos in stripe_set:
                intruder_frac = min(1.0, stripe.p1_intruder_ms / INTRUDER_GRACE_MS)

            if intruder_frac > 0:
                warn_col = (int(220 * intruder_frac), 0, 0)
                s = self.stroke_length
                for cx, cy in stripe.cells:
                    x0, y0 = self._cell_top_left(cx, cy)
                    pygame.draw.rect(
                        self.canvas, warn_col,
                        (x0, y0, self.cell_length, self.cell_length), 2)

    def _on_panel_extras(self, x: int, y: int) -> int:
        pygame.draw.line(self.info_canvas, (80, 80, 100),
                         (x, y), (self.info_width - x, y), 1)
        y += 12
        for i, stripe in enumerate(self.stripes):
            col   = self.p1_colour if stripe.owner == "p1" else self.p2_colour
            label = "P1" if stripe.owner == "p1" else "P2"
            pygame.draw.circle(self.info_canvas, col, (x + 8, y + 9), 7)
            self.info_canvas.blit(
                self.font.render(f"Stripe {i+1}: {label}'s turn",
                                 True, self.text_colour), (x + 22, y))
            y += 22
        return y + 6
