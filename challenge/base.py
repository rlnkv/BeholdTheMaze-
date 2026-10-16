"""
Shared base class for all Challenge Mode levels.
"""

import math
import os
from typing import List, Optional, Tuple

import pygame

try:
    import game_sounds as sounds
except ImportError:
    # No sounds module found — create a silent stand-in so the rest
    # of the code can call sounds.play() without any changes.
    class sounds:  # type: ignore
        @staticmethod
        def init() -> None: pass
        @staticmethod
        def play(name: str) -> None: pass

from maze import Cell, Maze
from render_utils import (
    cell_center,
    cell_top_left,
    dim_colour,
    draw_side_of_cell,
    load_font,
    recalculate_geometry,
)


class ChallengeRenderer:
    """
    Shared base class for the 2-player race mode.

    Subclasses (Level1Renderer, Level2Renderer, Level3Renderer) set a
    few class attributes (MAZE_SIZE, PALETTE_INDEX, LEVEL_NUMBER,
    LEVEL_NAME) and override hook methods for whatever makes that
    level special.

    All levels share:
      * Fast animated thin-line path reveal (not filled squares).
      * Fading 5-cell trace per player, offset left / right of center.
      * Split-circle avatar when both players share a cell.
      * P1 soft-purple / P2 warm-gold, readable on every palette.
    """

    # subclasses override these four
    LEVEL_NUMBER: int = 0
    LEVEL_NAME: str = ""
    MAZE_SIZE: Tuple[int, int] = (20, 20)
    PALETTE_INDEX: int = 0

    # path-reveal line speed (ms per step) — fast flash
    REVEAL_LINE_DELAY_MS = 18

    # pause after line completes before hiding
    REVEAL_HOLD_MS = 600

    # player colours readable on all four palettes
    P1_COLOUR = (180, 100, 220)   # soft purple
    P2_COLOUR = (220, 175,  30)   # warm gold

    # fading trace settings
    TRACE_LEN    = 8   # footprints kept in trail (more than lines so the path reads)
    TRACE_OFFSET = 4   # px left/right offset from cell center (still used for chaser)

    def __init__(self,
                 maze: Maze,
                 entry: Tuple[int, int],
                 exit: Tuple[int, int],
                 path: Tuple[List[Cell], List[str]],
                 screen: pygame.Surface,
                 palettes: list) -> None:

        self.maze = maze
        self.entry = entry
        self.exit = exit
        self.path = path
        self.level = self.LEVEL_NUMBER
        self.screen = screen

        self.window_width, self.window_height = screen.get_size()
        self.info_width = 300
        self.min_padding = 20
        self.maze_area_width = self.window_width - self.info_width
        self.maze_area_height = self.window_height

        self.canvas = pygame.Surface((self.maze_area_width,
                                       self.maze_area_height))
        self.info_canvas = pygame.Surface((self.info_width,
                                            self.window_height))

        here = os.path.dirname(os.path.abspath(__file__))
        self.font       = load_font(20, here)
        self.font_title = load_font(28, here)

        # pick palette by level
        p = palettes[self.PALETTE_INDEX]
        self.bg_colour = p["bg"]
        self.wall_colour = p["wall"]
        self.entry_colour = p["entry"]
        self.exit_colour = p["exit"]
        self.path_colour = p["path"]
        self.protect_colour = p["pattern"]
        self.interior_colour = p["interior"]
        self.text_colour = (255, 255, 255)
        self.p1_colour = self.P1_COLOUR
        self.p2_colour = self.P2_COLOUR

        self._recalculate_geometry()

        # player state
        self.p1_pos = entry
        self.p2_pos = entry
        # traces — list of last TRACE_LEN positions before current
        self.p1_trace: List[Tuple[int, int]] = []
        self.p2_trace: List[Tuple[int, int]] = []

        # path-reveal animation (thin animated line, not filled cells)
        self.reveal_line_index = 0    # how far along the line is drawn
        self.reveal_line_timer = 0    # ms accumulator
        self.reveal_hold_timer = 0    # ms spent in post-line hold
        self.reveal_done = False

        # race state
        self.race_started = False
        self.elapsed_ms = 0
        self.winner: Optional[str] = None
        self.winner_time_ms = 0

        # both-players finish tracking — used by the default _check_winner
        # (all levels) and by the waiting indicator in the panel
        self.p1_finished = False
        self.p2_finished = False

        self.running = True
        self.result: Optional[str] = None
        self.clock = pygame.time.Clock()

    # ------------------------------------------------------------ geometry

    def _recalculate_geometry(self) -> None:
        (self.cell_length, self.stroke_length,
         self.padding_x_side, self.padding_y_side) = recalculate_geometry(
            self.maze_area_width, self.maze_area_height,
            self.maze.width, self.maze.height, self.min_padding,
        )

    # ------------------------------------------------------------ helpers

    def _cell_center(self, x: int, y: int) -> Tuple[int, int]:
        """Pixel center of maze cell (x, y)."""
        return cell_center(x, y, self.cell_length, self.stroke_length,
                            self.padding_x_side, self.padding_y_side)

    def _cell_top_left(self, x: int, y: int) -> Tuple[int, int]:
        return cell_top_left(x, y, self.cell_length, self.stroke_length,
                              self.padding_x_side, self.padding_y_side)

    @staticmethod
    def _dim(colour: Tuple[int, int, int], alpha: int) -> Tuple[int, int, int]:
        """Darken colour by alpha (255 = full, 0 = black)."""
        return dim_colour(colour, alpha)

    # ------------------------------------------------------------ movement

    def _try_move(self, pos: Tuple[int, int], direction: str,
                  player: str = "") -> Tuple[int, int]:
        """
        Attempt to move from pos in direction. Returns the new position,
        or the original pos if blocked by a maze wall OR by the
        _is_move_blocked hook (used by level 4 for stripe blocking).

        `player` is "p1" or "p2" — passed to the hook so a subclass
        can block a specific player without touching movement logic here.
        """
        cell = self.maze.get_cell(*pos)
        if cell is None or cell.walls[direction]:
            return pos
        dx, dy = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}[direction]
        new_pos = (pos[0] + dx, pos[1] + dy)
        if self._is_move_blocked(player, new_pos):
            return pos
        return new_pos

    def _push_trace(self, trace: List, pos: Tuple[int, int]) -> List:
        """Append pos, keep only last TRACE_LEN entries."""
        return (trace + [pos])[-self.TRACE_LEN:]

    # ------------------------------------------------------------ hooks for levels to override

    def _on_update(self, dt_ms: int) -> None:
        """Hook: extra per-frame update logic. Default: nothing."""

    def _on_collect(self) -> None:
        """Hook: called after any player moves. Default: nothing."""

    def _on_draw_extras(self) -> None:
        """Hook: extra things to draw on the maze canvas. Default: nothing."""

    def _on_panel_extras(self, x: int, y: int) -> int:
        """
        Hook: extra rows in the side panel (e.g. score, chaser bar).
        Must return the new y position so the caller knows where the
        next panel section should start. Default: no change.
        """
        return y

    def _is_move_blocked(self, player: str, target_pos: Tuple[int, int]) -> bool:
        """
        Hook: return True to prevent `player` ("p1" or "p2") from
        moving to target_pos. Default: nothing is blocked.
        Level 4 overrides this to enforce stripe ownership rules.
        """
        return False

    def _check_winner(self) -> None:
        """
        Default win condition (all levels): BOTH players must reach
        the exit. The first to arrive waits; the clock stops when the
        second one arrives too.

        Level 3 still overrides this to add the Chaser loss condition
        on top. Level 4's override was identical to this and is now
        removed — it uses this default directly.
        """
        if self.winner is not None:
            return
        if self.p1_pos == self.exit:
            self.p1_finished = True
        if self.p2_pos == self.exit:
            self.p2_finished = True
        if self.p1_finished and self.p2_finished:
            self.winner = "Both players"
            self.winner_time_ms = self.elapsed_ms
            sounds.play("finish")

    # ------------------------------------------------------------ events

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                self.result = "menu"

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                    self.result = "menu"
                    continue

                if event.key == pygame.K_0:
                    # Debug shortcut: skip straight to the next level.
                    self.running = False
                    self.result = "next_level"
                    continue

                if self.winner is not None:
                    if event.key == pygame.K_RETURN:
                        self.running = False
                        self.result = "next_level"
                    continue

                if not self.race_started:
                    continue

                # Map keys -> (player_id, direction) for both players.
                KEY_MAP = {
                    pygame.K_UP:    ("p1", "N"),
                    pygame.K_DOWN:  ("p1", "S"),
                    pygame.K_LEFT:  ("p1", "W"),
                    pygame.K_RIGHT: ("p1", "E"),
                    pygame.K_w:     ("p2", "N"),
                    pygame.K_s:     ("p2", "S"),
                    pygame.K_a:     ("p2", "W"),
                    pygame.K_d:     ("p2", "E"),
                }
                if event.key not in KEY_MAP:
                    continue

                player, direction = KEY_MAP[event.key]
                if player == "p1":
                    new_pos = self._try_move(self.p1_pos, direction, "p1")
                    if new_pos != self.p1_pos:
                        self.p1_trace = self._push_trace(self.p1_trace, self.p1_pos)
                        sounds.play("step_p1")
                    self.p1_pos = new_pos
                else:
                    new_pos = self._try_move(self.p2_pos, direction, "p2")
                    if new_pos != self.p2_pos:
                        self.p2_trace = self._push_trace(self.p2_trace, self.p2_pos)
                        sounds.play("step_p2")
                    self.p2_pos = new_pos

                self._on_collect()
                self._check_winner()

    # ------------------------------------------------------------ update

    def _update(self, dt_ms: int) -> None:
        if not self.reveal_done:
            self._update_reveal(dt_ms)
            return

        if self.winner is None:
            self.elapsed_ms += dt_ms

        self._on_update(dt_ms)

    def _update_reveal(self, dt_ms: int) -> None:
        """Grow the animated path line step by step, then hold briefly."""
        path_len = len(self.path[0])
        if self.reveal_line_index < path_len - 1:
            self.reveal_line_timer += dt_ms
            steps = self.reveal_line_timer // self.REVEAL_LINE_DELAY_MS
            if steps:
                self.reveal_line_timer %= self.REVEAL_LINE_DELAY_MS
                old_index = self.reveal_line_index
                self.reveal_line_index = min(
                    self.reveal_line_index + steps, path_len - 1)
                self._on_reveal_advanced(old_index, self.reveal_line_index)
        else:
            # line finished — wait REVEAL_HOLD_MS then start the race
            self.reveal_hold_timer += dt_ms
            if self.reveal_hold_timer >= self.REVEAL_HOLD_MS:
                self.reveal_done = True
                self.race_started = True

    def _on_reveal_advanced(self, old_index: int, new_index: int) -> None:
        """
        Hook: called whenever the reveal line moves forward, with the
        old and new reveal_line_index. Level 2 uses this to drop
        collectables as the line passes them. Default: nothing.
        """

    # ------------------------------------------------------------ drawing

    def _draw_side_of_cell(self, surface: pygame.Surface,
                            colour: Tuple[int, int, int],
                            direction: str, x0: int, y0: int) -> None:
        draw_side_of_cell(surface, colour, direction, x0, y0,
                           self.cell_length, self.stroke_length)

    def _draw_maze(self) -> None:
        """Draw walls and cell fills — no path colouring during race."""
        self.canvas.fill(self.bg_colour)
        for row in range(self.maze.height):
            for col in range(self.maze.width):
                x0, y0 = self._cell_top_left(col, row)
                cell = self.maze.get_cell(col, row)
                for corner in ("NE", "SE", "SW", "NW"):
                    self._draw_side_of_cell(self.canvas, self.wall_colour,
                                             corner, x0, y0)
                if cell:
                    for d in cell.walls:
                        c = (self.wall_colour if cell.walls[d]
                             else self.interior_colour)
                        self._draw_side_of_cell(self.canvas, c, d, x0, y0)

                if (col, row) == self.entry:
                    fill = self.entry_colour
                elif (col, row) == self.exit:
                    fill = self.exit_colour
                elif cell and cell.is_pattern:
                    fill = self.protect_colour
                else:
                    fill = self.interior_colour

                s = self.stroke_length
                pygame.draw.rect(
                    self.canvas, fill,
                    (x0 + s, y0 + s, self.cell_length - 2 * s,
                     self.cell_length - 2 * s))

    def _draw_reveal_line(self) -> None:
        """Animated thin line growing from entry to current reveal head."""
        cells = self.path[0]
        if len(cells) < 2:
            return
        pts = [self._cell_center(c.x, c.y)
               for c in cells[:self.reveal_line_index + 1]]
        if len(pts) >= 2:
            # glow layer (wider, dimmer)
            pygame.draw.lines(
                self.canvas,
                self._dim(self.path_colour, 100),
                False, pts,
                max(2, self.cell_length // 5))
            # bright core
            pygame.draw.lines(
                self.canvas,
                self.path_colour,
                False, pts,
                max(1, self.cell_length // 8))
        # white dot at the leading head
        head = pts[-1]
        pygame.draw.circle(self.canvas, (255, 255, 255), head,
                            max(2, self.cell_length // 5))

    @staticmethod
    def _travel_direction(from_pos: Tuple[int, int],
                          to_pos: Tuple[int, int]) -> str:
        """Return the cardinal direction travelled from from_pos to to_pos."""
        dx = to_pos[0] - from_pos[0]
        dy = to_pos[1] - from_pos[1]
        if abs(dx) >= abs(dy):
            return "E" if dx >= 0 else "W"
        return "S" if dy >= 0 else "N"

    def _draw_footprint(
        self,
        cx: int, cy: int,
        direction: str,
        left_foot: bool,
        colour: Tuple[int, int, int],
        alpha: int,
    ) -> None:
        """
        Draw one tiny footprint at pixel position (cx, cy).

        The print is two overlapping ellipses (heel + toe ball) oriented
        in `direction`, mirrored for left vs right foot.

        Size is proportional to cell_length so it always fits inside
        the cell without touching walls.
        """
        c = self._dim(colour, alpha)
        size = max(2, self.cell_length // 7)  # radius of heel ellipse
        toe  = max(1, size * 2 // 3)          # radius of toe ball

        # Unit vectors along and across the direction of travel.
        # "across" is 90° counter-clockwise from along, which corresponds
        # to the player's LEFT when facing the direction of travel.
        along  = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}[direction]
        across = (along[1], -along[0])   # 90° CCW = player's left side

        # Lateral offset: +1 = player's left, -1 = player's right
        side = 1 if left_foot else -1
        lx = cx + side * across[0] * size
        ly = cy + side * across[1] * size

        # Heel centre — slightly behind the print
        hx = int(lx - along[0] * size * 0.4)
        hy = int(ly - along[1] * size * 0.4)

        # Toe centre — slightly ahead of centre
        tx = int(lx + along[0] * size * 0.7)
        ty = int(ly + along[1] * size * 0.7)

        # Draw heel (larger oval) and toe ball (smaller oval)
        # pygame.draw.ellipse needs a Rect; we fake it with circle for simplicity
        # at small sizes circles and ovals are visually identical.
        pygame.draw.circle(self.canvas, c, (hx, hy), size)
        pygame.draw.circle(self.canvas, c, (tx, ty), toe)

    def _draw_footprints(
        self,
        trace: List[Tuple[int, int]],
        colour: Tuple[int, int, int],
        step_offset: int = 0,   # added to step index for left/right alternation
    ) -> None:
        """
        Draw a fading trail of footprints along the trace positions.

        trace[0] is the oldest position (most faded), trace[-1] is the
        most recent (most opaque, closest to the player's current position).
        Footprints alternate left/right foot and are oriented in the
        direction of travel between consecutive trace cells.
        """
        if not trace:
            return
        n = len(trace)
        for i, pos in enumerate(trace):
            fade_t = (i + 1) / n        # 0=oldest, 1=newest
            alpha  = int(20 + 140 * fade_t)
            left_foot = ((i + step_offset) % 2 == 0)

            # Determine travel direction: look ahead if possible, else back
            if i + 1 < n:
                direction = self._travel_direction(pos, trace[i + 1])
            elif i > 0:
                direction = self._travel_direction(trace[i - 1], pos)
            else:
                direction = "E"   # single footprint: arbitrary direction

            cx, cy = self._cell_center(*pos)
            self._draw_footprint(cx, cy, direction, left_foot, colour, alpha)

    def _draw_players(self) -> None:
        """
        Circles for both players; split half-half when on same cell.

        Each half is a true semicircle arc walked from top to bottom
        on one side of the vertical diameter, then mirrored for the
        other half, so the two halves meet cleanly without folding
        back on themselves.
        """
        r = max(3, self.cell_length // 3)

        if self.p1_pos == self.p2_pos:
            cx, cy = self._cell_center(*self.p1_pos)
            steps = 16
            arc = [
                (cx - int(r * math.sin(math.pi * i / steps)),
                 cy - int(r * math.cos(math.pi * i / steps)))
                for i in range(steps + 1)
            ]  # (cx, cy-r) down the LEFT side to (cx, cy+r)

            left_pts = arc
            right_pts = [(2 * cx - x, y) for x, y in arc]  # mirror -> bulges right

            pygame.draw.polygon(self.canvas, self.p1_colour, left_pts)
            pygame.draw.polygon(self.canvas, self.p2_colour, right_pts)
            pygame.draw.line(self.canvas, (255, 255, 255),
                              (cx, cy - r), (cx, cy + r), 1)
            pygame.draw.circle(self.canvas, (255, 255, 255), (cx, cy), r, 1)
        else:
            for pos, colour in ((self.p1_pos, self.p1_colour),
                                 (self.p2_pos, self.p2_colour)):
                cx, cy = self._cell_center(*pos)
                pygame.draw.circle(self.canvas, colour, (cx, cy), r)
                pygame.draw.circle(self.canvas, (255, 255, 255), (cx, cy), r, 1)

    def _draw_stripe_ribbon(
        self,
        stripe_cells: List[Tuple[int, int]],
        path_start_idx: int,
        colour_a: Tuple[int, int, int],
        colour_b: Optional[Tuple[int, int, int]] = None,
        alpha: int = 160,
        alpha_b: int = 160,
    ) -> None:
        """
        Draw a continuous ribbon through the stripe cells, following
        the exact route of the solution path.

        Each cell gets a band running from its entry edge to its exit
        edge (with a small `gap` inset from each wall), so the ribbon
        reads as a painted line on the floor rather than filled squares.
        At corners the band is drawn in two overlapping pieces
        (entry-to-centre, then centre-to-exit) so the turn fills cleanly.

        If colour_b is given the ribbon is split along its travel axis:
          - N/S travel  → left half colour_a, right half colour_b
          - E/W travel  → top half colour_a, bottom half colour_b
        At corners each piece uses the axis of its own segment.
        """
        if not stripe_cells:
            return

        dirs = self.path[1]   # dirs[i] = direction from path cell i to i+1

        # Gap from each wall edge: must be at least stroke_length so the
        # ribbon never overlaps the wall rectangle.
        gap  = self.stroke_length + 2
        band = max(3, self.cell_length // 3)
        half = band // 2

        OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}

        # pixel offset from cell centre toward a direction
        def _offset(direction: str, dist: int) -> Tuple[int, int]:
            return {
                "N": (0, -dist), "S": (0, dist),
                "E": (dist, 0),  "W": (-dist, 0),
            }[direction]

        def _draw_segment(
            cx: int, cy: int,
            from_dir: Optional[str],
            to_dir: Optional[str],
            col_a: Tuple[int, int, int],
            col_b: Optional[Tuple[int, int, int]],
        ) -> None:
            """
            Draw one cell's worth of ribbon from from_dir side to to_dir side.
            `from_dir` is where we entered (None = start of stripe, open end).
            `to_dir`   is where we exit  (None = end of stripe, open end).
            """
            cl   = self.cell_length
            half_cl = cl // 2

            # reach: how far the band extends from centre toward each edge,
            # minus the gap so it doesn't touch the wall.
            reach = half_cl - gap

            def _rect_for_direction(direction: str) -> pygame.Rect:
                """Rectangle from centre to one wall side (with gap)."""
                ox, oy = _offset(direction, 1)
                # along the travel axis: full reach
                # perpendicular: half the band width
                if direction in ("N", "S"):
                    return pygame.Rect(
                        cx - half + 1, cy if direction == "S" else cy - reach,
                        band - 1, reach,
                    )
                else:  # E / W
                    return pygame.Rect(
                        cx if direction == "E" else cx - reach,
                        cy - half + 1,
                        reach, band - 1,
                    )

            def _fill_rect(rect: pygame.Rect, travel: Optional[str],
                           ca: Tuple[int, int, int],
                           cb: Optional[Tuple[int, int, int]]) -> None:
                """Fill a rect, optionally split by travel axis."""
                if cb is None or rect.width == 0 or rect.height == 0:
                    pygame.draw.rect(self.canvas, ca, rect)
                    return
                # split perpendicular to travel direction
                if travel in ("N", "S"):
                    # travelling vertically → divide left/right
                    w2 = rect.width // 2
                    pygame.draw.rect(self.canvas, ca,
                                     pygame.Rect(rect.x, rect.y, w2, rect.height))
                    pygame.draw.rect(self.canvas, cb,
                                     pygame.Rect(rect.x + w2, rect.y,
                                                 rect.width - w2, rect.height))
                else:
                    # travelling horizontally → divide top/bottom
                    h2 = rect.height // 2
                    pygame.draw.rect(self.canvas, ca,
                                     pygame.Rect(rect.x, rect.y, rect.width, h2))
                    pygame.draw.rect(self.canvas, cb,
                                     pygame.Rect(rect.x, rect.y + h2,
                                                 rect.width, rect.height - h2))

            # centre square (always drawn)
            centre = pygame.Rect(cx - half + 1, cy - half + 1,
                                 band - 1, band - 1)
            # use to_dir as the dominant axis for the centre square
            dominant = to_dir or from_dir
            _fill_rect(centre, dominant, ca=col_a, cb=col_b)

            # arm toward where we came from
            if from_dir:
                r = _rect_for_direction(OPPOSITE[from_dir])
                _fill_rect(r, from_dir, ca=col_a, cb=col_b)

            # arm toward where we exit
            if to_dir:
                r = _rect_for_direction(to_dir)
                _fill_rect(r, to_dir, ca=col_a, cb=col_b)

        col_a = self._dim(colour_a, alpha)
        col_b = self._dim(colour_b, alpha_b) if colour_b else None

        for local_i, (sx, sy) in enumerate(stripe_cells):
            path_i = path_start_idx + local_i
            cx, cy = self._cell_center(sx, sy)

            # direction we came from (entry side of this cell)
            from_dir = OPPOSITE[dirs[path_i - 1]] if path_i > 0 and path_i - 1 < len(dirs) else None
            # direction we exit toward (exit side of this cell)
            to_dir   = dirs[path_i] if path_i < len(dirs) else None

            # clamp to stripe: first cell has no from, last has no to
            if local_i == 0:
                from_dir = None
            if local_i == len(stripe_cells) - 1:
                to_dir = None

            _draw_segment(cx, cy, from_dir, to_dir, col_a, col_b)

    def _draw_double_triangle(
        self,
        cx: int, cy: int,
        r: int,
        pointing_up: bool,
    ) -> None:
        """
        Draw two small triangles side-by-side (P1 colour left, P2 colour right)
        centered at (cx, cy) with size r.  Used as entry/exit markers on
        sync (two-colored) stripes.  pointing_up=True for entry, False for exit.
        """
        offset = r + 1   # horizontal gap between the two triangles
        for colour, sign in ((self.p1_colour, -1), (self.p2_colour, 1)):
            px = cx + sign * offset
            if pointing_up:
                tri = [(px, cy - r), (px - r, cy + r), (px + r, cy + r)]
            else:
                tri = [(px, cy + r), (px - r, cy - r), (px + r, cy - r)]
            pygame.draw.polygon(self.canvas, colour, tri)
            pygame.draw.polygon(self.canvas, (255, 255, 255), tri, 1)

    def _draw_chaser(self, chaser_index: int, chaser_trace: List[Tuple[int, int]]) -> None:
        """
        Draw the chaser's fading trail and pulsing red head dot.
        Shared by level 3 and level 6 so they don't duplicate this code.
        """
        self._draw_footprints(chaser_trace, (220, 50, 50), step_offset=1)

        if chaser_index < len(self.path[0]):
            cell = self.path[0][chaser_index]
            cx, cy = self._cell_center(cell.x, cell.y)
            r = max(3, self.cell_length // 3)
            pulse = abs((self.elapsed_ms % 600) - 300) / 300.0
            bright = int(180 + 75 * pulse)
            pygame.draw.circle(self.canvas, (bright, 30, 30), (cx, cy), r)
            pygame.draw.circle(self.canvas, (255, 80, 80), (cx, cy), max(1, r // 2))

    def _draw_panel(self) -> None:
        """Right-side info panel: level name, timer, legend, level extras."""
        self.info_canvas.fill((28, 28, 46))
        x, y = 20, 30

        title = self.font_title.render(
            f"Lvl {self.LEVEL_NUMBER} — {self.LEVEL_NAME}", True,
            self.text_colour)
        self.info_canvas.blit(title, (x, y))
        y += 46

        size_lbl = self.font.render(
            f"{self.maze.width} x {self.maze.height}", True, self.text_colour)
        self.info_canvas.blit(size_lbl, (x, y))
        y += 34

        pygame.draw.line(self.info_canvas, (80, 80, 100),
                          (x, y), (self.info_width - x, y), 1)
        y += 16

        # timer or reveal progress bar
        if not self.reveal_done:
            pct = self.reveal_line_index / max(1, len(self.path[0]) - 1)
            bar_w = self.info_width - 2 * x
            pygame.draw.rect(self.info_canvas, (60, 60, 80),
                              (x, y, bar_w, 8))
            pygame.draw.rect(self.info_canvas, self.path_colour,
                              (x, y, int(bar_w * pct), 8))
            y += 20
            self.info_canvas.blit(
                self.font.render("Memorize the path!", True, self.path_colour),
                (x, y))
            y += 30
        else:
            secs = self.elapsed_ms / 1000.0
            t_surf = self.font_title.render(f"{secs:0.1f}s", True,
                                             self.text_colour)
            self.info_canvas.blit(t_surf, (x, y))
            y += 46

        # player legend dots
        pygame.draw.circle(self.info_canvas, self.p1_colour, (x + 8, y + 10), 8)
        self.info_canvas.blit(
            self.font.render("P1  (arrows)", True, self.text_colour), (x + 24, y))
        y += 30
        pygame.draw.circle(self.info_canvas, self.p2_colour, (x + 8, y + 10), 8)
        self.info_canvas.blit(
            self.font.render("P2  (WASD)", True, self.text_colour), (x + 24, y))
        y += 36

        # level-specific panel rows (collectables score / chaser bar / stripes)
        y = self._on_panel_extras(x, y)

        # waiting indicator — shown as soon as one player reaches the exit
        # but before both have, so the waiting player knows what's happening
        if self.winner is None:
            if self.p1_finished and not self.p2_finished:
                pygame.draw.line(self.info_canvas, (80, 80, 100),
                                  (x, y), (self.info_width - x, y), 1)
                y += 10
                self.info_canvas.blit(
                    self.font.render("P1 at exit — waiting for P2",
                                      True, self.p1_colour), (x, y))
                y += 24
            elif self.p2_finished and not self.p1_finished:
                pygame.draw.line(self.info_canvas, (80, 80, 100),
                                  (x, y), (self.info_width - x, y), 1)
                y += 10
                self.info_canvas.blit(
                    self.font.render("P2 at exit — waiting for P1",
                                      True, self.p2_colour), (x, y))
                y += 24

        # winner / loss screen
        if self.winner is not None:
            pygame.draw.line(self.info_canvas, (80, 80, 100),
                              (x, y), (self.info_width - x, y), 1)
            y += 14
            if self.winner == "Chaser":
                msg1 = "Chaser wins!"
                msg2 = "Both players lose!"
                col  = (220, 50, 50)
            else:
                # "Both players" — all levels now finish cooperatively
                msg1 = "Both finish!"
                msg2 = f"Time: {self.winner_time_ms / 1000.0:0.1f}s"
                col  = (100, 220, 150)
            self.info_canvas.blit(
                self.font_title.render(msg1, True, col), (x, y))
            y += 38
            self.info_canvas.blit(
                self.font.render(msg2, True, self.text_colour), (x, y))
            y += 34
            self.info_canvas.blit(
                self.font.render("[ENTER] next level", True, (136, 192, 208)),
                (x, y))
            y += 24
            self.info_canvas.blit(
                self.font.render("[ESC] menu", True, (136, 192, 208)), (x, y))

        self.screen.blit(self.info_canvas, (self.maze_area_width, 0))

    def _render(self) -> None:
        self._draw_maze()
        if not self.reveal_done:
            # during reveal phase, only show the animated line
            self._draw_reveal_line()
        else:
            # race phase — traces, then level extras, then avatars on top
            self._draw_footprints(self.p1_trace, self.p1_colour, step_offset=0)
            self._draw_footprints(self.p2_trace, self.p2_colour, step_offset=1)
            self._on_draw_extras()
            self._draw_players()
        self.screen.blit(self.canvas, (0, 0))
        self._draw_panel()

    # ------------------------------------------------------------ main loop

    def run(self) -> Optional[str]:
        """
        Run the race until someone wins (or a level-specific loss
        condition triggers, e.g. the level 3 chaser reaching the exit).

        Returns:
            "next_level" -- advance to next level.
            "menu"       -- return to main menu.
            None         -- window closed.
        """
        while self.running:
            self._handle_events()
            dt = self.clock.tick(60)
            self._update(dt)
            self._render()
            pygame.display.flip()

        return self.result
