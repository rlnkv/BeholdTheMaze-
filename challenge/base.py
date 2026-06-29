"""
NEW FILE (this iteration).

This is the shared "race engine" for Challenge Mode. It used to be
one giant ChallengeRenderer class inside renderer.py, mixing
"things every level needs" (player movement, the reveal-line
animation, drawing walls) with "things only ONE level needs"
(collectable triangles for level 2, the chasing red dot for level 3).

ELI5: think of this class like a car CHASSIS — wheels, engine,
seats, steering wheel. Every car (every level) is built on top of
this same chassis. Level files (level1.py, level2.py, level3.py)
just bolt on their own extra parts by filling in a few "hook"
methods:

    _on_update(dt_ms)      -- anything extra to update each frame
    _on_collect()          -- called when a player steps on a cell
    _on_draw_extras()      -- anything extra to draw on the maze
    _on_panel_extras(y)    -- anything extra to draw in the side panel

If a level doesn't need one of these, it just doesn't override it,
and the chassis default (do nothing) is used.
"""

import math
import os
from typing import List, Optional, Tuple

import pygame

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
    TRACE_LEN = 5      # cells kept in trail
    TRACE_OFFSET = 4   # px left/right offset from cell center

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
        self.font = load_font(20, here)
        self.font_big = load_font(40, here)
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

    def _try_move(self, pos: Tuple[int, int], direction: str) -> Tuple[int, int]:
        cell = self.maze.get_cell(*pos)
        if cell is None or cell.walls[direction]:
            return pos
        dx, dy = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}[direction]
        return (pos[0] + dx, pos[1] + dy)

    def _push_trace(self, trace: List, pos: Tuple[int, int]) -> List:
        """Append pos, keep only last TRACE_LEN entries."""
        return (trace + [pos])[-self.TRACE_LEN:]

    # ------------------------------------------------------------ hooks for levels to override

    def _on_update(self, dt_ms: int) -> None:
        """Hook: extra per-frame update logic. Default: nothing."""

    def _on_collect(self) -> None:
        """Hook: called after a player moves. Default: nothing."""

    def _on_draw_extras(self) -> None:
        """Hook: extra things to draw on the maze canvas. Default: nothing."""

    def _on_panel_extras(self, x: int, y: int) -> int:
        """
        Hook: extra rows in the side panel (e.g. score, chaser bar).
        Must return the new y position so the caller knows where the
        next panel section should start. Default: no change.
        """
        return y

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

                if self.winner is not None:
                    if event.key == pygame.K_RETURN:
                        self.running = False
                        self.result = "next_level"
                    continue

                if not self.race_started:
                    continue

                # Player 1 — arrow keys
                new1 = None
                if event.key == pygame.K_UP:
                    new1 = self._try_move(self.p1_pos, "N")
                elif event.key == pygame.K_DOWN:
                    new1 = self._try_move(self.p1_pos, "S")
                elif event.key == pygame.K_LEFT:
                    new1 = self._try_move(self.p1_pos, "W")
                elif event.key == pygame.K_RIGHT:
                    new1 = self._try_move(self.p1_pos, "E")

                if new1 is not None:
                    if new1 != self.p1_pos:
                        self.p1_trace = self._push_trace(self.p1_trace, self.p1_pos)
                    self.p1_pos = new1

                # Player 2 — WASD
                new2 = None
                if event.key == pygame.K_w:
                    new2 = self._try_move(self.p2_pos, "N")
                elif event.key == pygame.K_s:
                    new2 = self._try_move(self.p2_pos, "S")
                elif event.key == pygame.K_a:
                    new2 = self._try_move(self.p2_pos, "W")
                elif event.key == pygame.K_d:
                    new2 = self._try_move(self.p2_pos, "E")

                if new2 is not None:
                    if new2 != self.p2_pos:
                        self.p2_trace = self._push_trace(self.p2_trace, self.p2_pos)
                    self.p2_pos = new2

                if new1 is not None or new2 is not None:
                    self._on_collect()
                    self._check_winner()

    def _check_winner(self) -> None:
        if self.winner is not None:
            return
        if self.p1_pos == self.exit:
            self.winner = "Player 1"
            self.winner_time_ms = self.elapsed_ms
        elif self.p2_pos == self.exit:
            self.winner = "Player 2"
            self.winner_time_ms = self.elapsed_ms

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

    def _draw_trace(self, trace: List[Tuple[int, int]],
                     colour: Tuple[int, int, int], offset_x: int) -> None:
        """Thin fading line following the player, offset left or right."""
        if len(trace) < 2:
            return
        n = len(trace)
        for i in range(n - 1):
            alpha = int(30 + 150 * (i + 1) / n)   # fades from old to new
            c = self._dim(colour, alpha)
            p0 = (self._cell_center(*trace[i])[0] + offset_x,
                  self._cell_center(*trace[i])[1])
            p1 = (self._cell_center(*trace[i + 1])[0] + offset_x,
                  self._cell_center(*trace[i + 1])[1])
            pygame.draw.line(self.canvas, c, p0, p1,
                              max(1, self.cell_length // 8))

    def _draw_players(self) -> None:
        """Circles for both players; split half-half when on same cell."""
        r = max(3, self.cell_length // 3)

        if self.p1_pos == self.p2_pos:
            # vertically split circle — left=P1, right=P2
            cx, cy = self._cell_center(*self.p1_pos)
            left_pts = ([(cx, cy - r)] +
                        [(cx + int(r * math.cos(a)),
                          cy - int(r * math.sin(a)))
                         for a in [math.pi * i / 8 for i in range(8, 17)]] +
                        [(cx, cy + r)])
            right_pts = ([(cx, cy - r)] +
                         [(cx + int(r * math.cos(a)),
                           cy - int(r * math.sin(a)))
                          for a in [math.pi * i / 8 for i in range(0, 9)]] +
                         [(cx, cy + r)])
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

        # level-specific panel rows (collectables score / chaser bar)
        y = self._on_panel_extras(x, y)

        # winner / loss screen
        if self.winner is not None:
            pygame.draw.line(self.info_canvas, (80, 80, 100),
                              (x, y), (self.info_width - x, y), 1)
            y += 14
            if self.winner == "Chaser":
                msg1, msg2, col = ("Chaser wins!",
                                    "Both players lose!", (220, 50, 50))
            else:
                msg1 = f"{self.winner} wins!"
                msg2 = f"Time: {self.winner_time_ms / 1000.0:0.1f}s"
                col = (249, 240, 2)
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
            self._draw_trace(self.p1_trace, self.p1_colour, -self.TRACE_OFFSET)
            self._draw_trace(self.p2_trace, self.p2_colour, self.TRACE_OFFSET)
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
