import pygame
import random
from typing import List, Tuple, Optional
from maze import Maze, Cell, add_42_pattern, HuntAndKillGenerator
from path_finder import PathFinder
from renderer import Renderer
from maze_utils import is_on_pattern, safe_random_cell, safe_random_entry_exit  # NEW: shared helpers, replace local copies below
from render_utils import load_font as _shared_load_font  # NEW: shared font loader
import os

def _load_font(size: int) -> pygame.font.Font:
    """Thin wrapper so the rest of this file doesn't change: loads a
    font using the shared render_utils helper instead of its own
    duplicated candidate-list logic."""
    here = os.path.dirname(os.path.abspath(__file__))
    return _shared_load_font(size, here)

#  Colors used in the menu (same dark theme as renderer)
BG_COLOR        = (46,  52,  64)   # dark background
PANEL_COLOR     = (28,  28,  46)   # slightly darker right panel
TEXT_COLOR      = (255, 255, 255)  # white  – normal text
SELECTED_COLOR  = (249, 240,   2)  # yellow – highlighted menu item
DIM_COLOR       = (120, 120, 140)  # grey   – locked / coming-soon items
HINT_COLOR      = (136, 192, 208)  # light blue – small hint text
ERROR_COLOR     = (255,  80,  80)  # red – validation errors

OPTION_RANDOM   = 0
OPTION_CUSTOM   = 1
OPTION_CHALLENGE = 2
OPTION_QUIT     = 3


class MenuScreen:
    """
    Draws and runs the main menu before the maze starts.

    Layout (fullscreen window):
      Left side  (screen_width - 300 px) - animated background maze
      Right side (300px wide)            - menu options panel

    The user navigates with UP/DOWN arrows and confirms with ENTER.
    After a choice is made, the menu returns a Config-like object
    that a_maze_ing.py can pass straight into MazeGenerator.

    Attributes:
        screen         - the pygame window (shared with Renderer later)
        selected_index - which menu item the cursor is on right now
        running        - False when the user pressed ENTER or ESC
        result         - filled in once the user confirms a choice;
                         contains (width, height, entry, exit, seed)
                         or None if the user quit
    """

    PANEL_WIDTH = 300

    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen

        self.window_width, self.window_height = screen.get_size()
        self.maze_area_width = self.window_width - self.PANEL_WIDTH

        self.font_title  = _load_font(35)
        self.font_option = _load_font(26)
        self.font_hint   = _load_font(15)

        # Menu state
        self.selected_index = OPTION_RANDOM
        self.running = True
        self.result: Optional[Tuple] = None

        # Sub-menu state
        self.custom_fields = [
            "Width", "Height",
            "Entry X", "Entry Y",
            "Exit X", "Exit Y",
            "Generate",
            "Back",
        ]

        # default values for the six numeric fields (Generate/Back have none)
        self.custom_values = [" ", " ", " ", " ", " ", " "]
        self.custom_cursor = 0
        self.custom_error  = ""

        # index constants for the two action rows so the logic below
        # stays readable even if we ever reorder the list.
        self.GENERATE_INDEX = self.custom_fields.index("Generate")
        self.BACK_INDEX     = self.custom_fields.index("Back")

        # decorative background maze
        bg_maze, bg_path, bg_entry, bg_exit = self._make_bg_maze()
        self.bg_renderer = Renderer(
            maze   = bg_maze,
            path   = bg_path,
            entry  = bg_entry,
            exit   = bg_exit,
            screen = self.screen,
        )
        self.bg_renderer.show_path = True

        # Panel surface (right side only)
        self.panel_surface = pygame.Surface((self.PANEL_WIDTH,
                                             self.window_height))

    # ── background maze ───────────────────────────────────────────────────

    def _make_bg_maze(self) -> Tuple[Maze, Tuple, Tuple[int, int],
                                     Tuple[int, int]]:
        """
        Generate a maze sized to fill the background area with small cells.
        Same seed every time so it looks intentional, not noisy.
        """
        # Size the bg maze so cells are ~10px, but cap at 40x40.
        # A bigger maze takes too long to generate AND to render each frame,
        # which starves the event loop and makes the menu feel frozen.
        target_cell_px = 10
        width  = min(40, max(9,  self.maze_area_width  // target_cell_px))
        height = min(30, max(7,  self.window_height    // target_cell_px))

        seed = 42
        maze = Maze(width, height)
        add_42_pattern(maze)
        HuntAndKillGenerator(seed).generate(maze)

        entry      = (0, 0)
        exit_      = (width - 1, height - 1)
        entry_cell = maze.get_cell(*entry)
        exit_cell  = maze.get_cell(*exit_)
        path       = PathFinder(maze).find_path(entry_cell, exit_cell)
        return maze, path, entry, exit_

    def _draw_background_maze(self) -> None:
        """
        Draw the background maze on the left side of the menu.

        passes draw_panel=False so the renderer does NOT draw its
        own right-side info panel underneath the menu panel.
        That was the blinking glitch: the renderer's panel was drawn
        first, then the menu panel was drawn on top, and the brief
        overlap every frame caused the visible flicker.
        """
        self.bg_renderer._render(draw_panel=False)

    # ── main menu panel ───────────────────────────────────────────────────

    def _draw_main_panel(self) -> None:
        """
        Draw the right-side panel with menu options and hints.

        Visual hierarchy:
          PRIMARY   (large, bright)  — Challenge Mode, Quit
          SECONDARY (small, dim)     — Random Maze, Custom Maze
        """
        self.panel_surface.fill(PANEL_COLOR)
        x = 20
        y = 50

        title = self.font_title.render("A-MAZE-ING", True, TEXT_COLOR)
        self.panel_surface.blit(title, (x, y))
        y += 50

        pygame.draw.line(self.panel_surface, DIM_COLOR,
                         (x, y), (self.PANEL_WIDTH - x, y), 1)
        y += 20

        # Secondary options — smaller font, dimmer colour
        secondary = [
            (OPTION_RANDOM, "Random Maze"),
            (OPTION_CUSTOM, "Custom Maze"),
        ]
        for idx, label in secondary:
            selected = (idx == self.selected_index)
            arrow = "▶ " if selected else "   "
            color = SELECTED_COLOR if selected else DIM_COLOR
            surf = self.font_hint.render(arrow + label, True, color)
            self.panel_surface.blit(surf, (x, y))
            y += 26

        y += 16
        pygame.draw.line(self.panel_surface, DIM_COLOR,
                         (x, y), (self.PANEL_WIDTH - x, y), 1)
        y += 24

        # Primary options — large font, full brightness
        primary = [
            (OPTION_CHALLENGE, "Challenge Mode"),
            (OPTION_QUIT,      "Quit"),
        ]
        for idx, label in primary:
            selected = (idx == self.selected_index)
            arrow = "▶  " if selected else "    "
            color = SELECTED_COLOR if selected else TEXT_COLOR
            surf = self.font_option.render(arrow + label, True, color)
            self.panel_surface.blit(surf, (x, y))
            y += 56

        y += 10
        pygame.draw.line(self.panel_surface, DIM_COLOR,
                         (x, y), (self.PANEL_WIDTH - x, y), 1)
        y += 20

        hints = [("↑ ↓", "navigate"), ("ENTER", "confirm")]
        for key, desc in hints:
            self.panel_surface.blit(
                self.font_hint.render(f"[{key}]", True, HINT_COLOR), (x, y))
            self.panel_surface.blit(
                self.font_hint.render(desc, True, TEXT_COLOR), (x + 80, y))
            y += 26

        self.screen.blit(self.panel_surface, (self.maze_area_width, 0))

    # ── custom maze panel ─────────────────────────────────────────────────

    def _draw_custom_panel(self) -> None:
        """
        Draw the right-side panel for the custom maze input screen.
        Shows six text fields (width, height, entry x/y, exit x/y),
        then a Generate button and a Back button.
        The currently active row has a yellow border / arrow.
        """
        self.panel_surface.fill(PANEL_COLOR)
        x = 20
        y = 40

        # title
        title = self.font_title.render("Create your MAZE", True, TEXT_COLOR)
        self.panel_surface.blit(title, (x, y))
        y += 40

        # ── six input fields ──────────────────────────────────────────────
        # custom_fields[:-2] are the text boxes ("Width" … "Exit Y").
        # The last two ("Generate", "Back") are drawn as action rows below.
        num_inputs = self.GENERATE_INDEX   # = 6

        for i in range(num_inputs):
            label    = self.custom_fields[i]
            value    = self.custom_values[i]
            is_active = (i == self.custom_cursor)

            # label
            label_color = SELECTED_COLOR if is_active else TEXT_COLOR
            label_surf  = self.font_option.render(label + ":", True, label_color)
            self.panel_surface.blit(label_surf, (x, y))
            y += 30

            # input box
            box_rect     = pygame.Rect(x, y, self.PANEL_WIDTH - 2 * x, 30)
            border_color = SELECTED_COLOR if is_active else DIM_COLOR
            pygame.draw.rect(self.panel_surface, PANEL_COLOR, box_rect)
            pygame.draw.rect(self.panel_surface, border_color, box_rect, 2)

            display_text = value + ("|" if is_active else "")
            val_surf = self.font_hint.render(display_text, True, TEXT_COLOR)
            self.panel_surface.blit(val_surf, (x + 6, y + 6))
            y += 40

        # ── separator ─────────────────────────────────────────────────────
        y += 6
        pygame.draw.line(
            self.panel_surface, DIM_COLOR,
            (x, y), (self.PANEL_WIDTH - x, y), 1
        )
        y += 12

        # ── Generate button  ─────────────────────────────────────────
        is_gen_active  = (self.custom_cursor == self.GENERATE_INDEX)
        gen_arrow      = "▶  " if is_gen_active else "   "
        gen_color      = SELECTED_COLOR if is_gen_active else TEXT_COLOR
        gen_surf       = self.font_option.render(gen_arrow + "Generate",
                                                 True, gen_color)
        self.panel_surface.blit(gen_surf, (x, y))
        y += 44

        # ── Back button ───────────────────────────────────────────────────
        is_back_active = (self.custom_cursor == self.BACK_INDEX)
        back_arrow     = "▶  " if is_back_active else "   "
        back_color     = SELECTED_COLOR if is_back_active else TEXT_COLOR
        back_surf      = self.font_option.render(back_arrow + "Back",
                                                 True, back_color)
        self.panel_surface.blit(back_surf, (x, y))
        y += 44

        # ── error message ─────────────────────────────────────────────────
        if self.custom_error:
            words = self.custom_error.split()
            line, lines = "", []
            for w in words:
                if len(line) + len(w) + 1 > 28:
                    lines.append(line)
                    line = w
                else:
                    line = (line + " " + w).strip()
            if line:
                lines.append(line)
            y += 6
            for err_line in lines:
                err_surf = self.font_hint.render(err_line, True, ERROR_COLOR)
                self.panel_surface.blit(err_surf, (x, y))
                y += 22

        # ── key hints (pinned to bottom) ──────────────────────────────────
        # use dynamic window_height instead of hardcoded 900.
        y = self.window_height - 120
        hints = [
            ("↑ ↓",   "switch field"),
            ("ENTER", "confirm / next"),
        ]
        for key, desc in hints:
            key_surf  = self.font_hint.render(f"[{key}]", True, HINT_COLOR)
            desc_surf = self.font_hint.render(desc, True, TEXT_COLOR)
            self.panel_surface.blit(key_surf,  (x,      y))
            self.panel_surface.blit(desc_surf, (x + 80, y))
            y += 26

        self.screen.blit(self.panel_surface, (self.maze_area_width, 0))

    # ── helpers ───────────────────────────────────────────────────────────

    def _parse_or_random(self, value: str, lo: int, hi: int) -> int:
        """
        Parse an integer from a field, or pick randomly if "-" or empty.
        lo/hi are the inclusive random range used when the field is blank.
        """
        if value.strip() in ("-", ""):
            return random.randint(lo, hi)
        return int(value.strip())

    # NEW: _is_on_pattern and _safe_random_cell used to be duplicated
    # here as methods. They now live in maze_utils.py (imported at the
    # top of this file as is_on_pattern / safe_random_cell) so menu.py,
    # renderer.py, and challenge/runner.py all share one copy.

    def _validate_custom_inputs(self) -> bool:
        """
        Check that the six custom fields produce a valid maze.
        Fields left as "-" are filled with random-but-valid values.
        Sets self.custom_error and returns False on any problem.
        """
        try:
            # Random default range capped at 30x20 so an all-"-" Generate
            # still produces a fast maze. User can type bigger values if
            # they want — the explicit limit check below lets up to 60x40.
            w = self._parse_or_random(self.custom_values[0], 9,  30)
            h = self._parse_or_random(self.custom_values[1], 7,  20)
        except ValueError:
            self.custom_error = "Width and height must be numbers."
            return False

        if w < 9:
            self.custom_error = "Width must be at least 9."
            return False
        if h < 7:
            self.custom_error = "Height must be at least 7."
            return False
        # Cap at 60x40 — beyond that generation is noticeably slow.
        if w > 60:
            self.custom_error = "Max width is 60."
            return False
        if h > 40:
            self.custom_error = "Max height is 40."
            return False

        try:
            ex = self._parse_or_random(self.custom_values[2], 0, w - 1)
            ey = self._parse_or_random(self.custom_values[3], 0, h - 1)
            fx = self._parse_or_random(self.custom_values[4], 0, w - 1)
            fy = self._parse_or_random(self.custom_values[5], 0, h - 1)
        except ValueError:
            self.custom_error = "Coordinates must be numbers or -."
            return False

        if not (0 <= ex < w and 0 <= ey < h):
            self.custom_error = "Entry is outside the maze."
            return False
        if not (0 <= fx < w and 0 <= fy < h):
            self.custom_error = "Exit is outside the maze."
            return False
        if (ex, ey) == (fx, fy):
            self.custom_error = "Entry and exit must differ."
            return False

        # Build a test maze to check the pattern cell positions.
        test_maze = Maze(w, h)
        add_42_pattern(test_maze)

        # If the user typed coordinates that land on the pattern, error.
        # But if the value was left as "-" (random), silently re-roll until
        # we find a free cell — no error message needed.
        entry_was_random = self.custom_values[2].strip() in (" ", "") or                            self.custom_values[3].strip() in ("-", "")
        exit_was_random  = self.custom_values[4].strip() in (" ", "") or                            self.custom_values[5].strip() in ("-", "")

        if is_on_pattern(test_maze, ex, ey):
            if entry_was_random:
                # silently pick again until off-pattern
                ex, ey = safe_random_cell(test_maze, w, h)
            else:
                self.custom_error = (
                    f"Entry ({ex},{ey}) is on the 42 pattern. "
                    "Pick a different cell."
                )
                return False

        if is_on_pattern(test_maze, fx, fy):
            if exit_was_random:
                # silently pick again until off-pattern
                fx, fy = safe_random_cell(test_maze, w, h)
            else:
                self.custom_error = (
                    f"Exit ({fx},{fy}) is on the 42 pattern. "
                    "Pick a different cell."
                )
                return False

        # guard: entry and exit still must differ after any re-rolls
        while (ex, ey) == (fx, fy):
            fx, fy = safe_random_cell(test_maze, w, h)

        # write resolved values back so user sees what was chosen
        self.custom_values[0] = str(w)
        self.custom_values[1] = str(h)
        self.custom_values[2] = str(ex)
        self.custom_values[3] = str(ey)
        self.custom_values[4] = str(fx)
        self.custom_values[5] = str(fy)

        self.custom_error = ""
        return True

    def _launch_custom_maze(self) -> None:
        """
        Validate inputs and store the result tuple so the main loop exits.
        Called both by ENTER on Generate and by ENTER on Exit Y.
        """
        if self._validate_custom_inputs():
            w    = int(self.custom_values[0])
            h    = int(self.custom_values[1])
            ex   = int(self.custom_values[2])
            ey   = int(self.custom_values[3])
            fx   = int(self.custom_values[4])
            fy   = int(self.custom_values[5])
            seed = random.randint(1, 10000)
            self.result  = (w, h, (ex, ey), (fx, fy), seed, False)
            self.running = False

    # ── key handlers ──────────────────────────────────────────────────────

    def _handle_main_menu_keys(self, event: pygame.event.Event) -> None:
        """
        React to key presses when the main menu is visible.
        UP/DOWN move the cursor, ENTER confirms the selection.
        """
        if event.key == pygame.K_UP:
            self.selected_index = (self.selected_index - 1) % (OPTION_QUIT + 1)

        elif event.key == pygame.K_DOWN:
            self.selected_index = (self.selected_index + 1) % (OPTION_QUIT + 1)

        elif event.key == pygame.K_RETURN:
            if self.selected_index == OPTION_RANDOM:
                # Keep random maze small so generation is fast (< 1 sec).
                # Large mazes freeze the screen because nothing is drawn
                # while HuntAndKillGenerator is running.
                w    = random.randint(15, 30)
                h    = random.randint(10, 20)
                seed = random.randint(1, 10000)
                # NEW: safe_random_entry_exit retries until entry/exit
                # land off the 42 pattern and differ from each other,
                # so they are never placed on a blocked cell.
                test_maze = Maze(w, h)
                add_42_pattern(test_maze)
                entry, exit_ = safe_random_entry_exit(test_maze, w, h)
                self.result  = (w, h, entry, exit_, seed, True)
                self.running = False

            elif self.selected_index == OPTION_CUSTOM:
                self.in_custom_menu = True
                self.custom_cursor  = 0
                self.custom_error   = ""

            elif self.selected_index == OPTION_CHALLENGE:
                self.result  = ("challenge", 1)   # NEW: level marker tuple
                self.running = False

            elif self.selected_index == OPTION_QUIT:
                self.running = False

    def _handle_custom_menu_keys(self, event: pygame.event.Event) -> None:
        """
        React to key presses inside the custom-maze input screen.

        UP/DOWN   - move between fields.
        Digits    - typed into the active text field.
        BACKSPACE - delete last character.
        ENTER on Generate - validate and start the maze.
        ENTER on Back     - return to the main menu.
        ENTER on any text field - advance to the next field.
        ESC       - return to the main menu.
        """
        num_inputs = self.GENERATE_INDEX   # number of text-input rows (6)

        if event.key == pygame.K_ESCAPE:
            self.in_custom_menu = False
            self.custom_error   = ""

        elif event.key == pygame.K_UP:
            self.custom_cursor = (
                self.custom_cursor - 1) % len(self.custom_fields)

        elif event.key == pygame.K_DOWN:
            self.custom_cursor = (
                self.custom_cursor + 1) % len(self.custom_fields)

        elif event.key == pygame.K_RETURN:
            if self.custom_cursor == self.BACK_INDEX:
                # "Back" — return to main menu
                self.in_custom_menu = False
                self.custom_error   = ""

            elif self.custom_cursor == self.GENERATE_INDEX:
                self._launch_custom_maze()

            else:
                # Any text field — advance cursor to the next row
                self.custom_cursor = (
                    self.custom_cursor + 1) % len(self.custom_fields)

        elif event.key == pygame.K_BACKSPACE:
            # delete only from text fields, not from Generate/Back
            if self.custom_cursor < num_inputs:
                self.custom_values[self.custom_cursor] = \
                    self.custom_values[self.custom_cursor][:-1]

        else:
            # type a digit into the active text field (not Generate/Back)
            char = event.unicode
            if char.isdigit() and self.custom_cursor < num_inputs:
                self.custom_values[self.custom_cursor] += char

    # ── main loop ─────────────────────────────────────────────────────────

    def run(self) -> Optional[Tuple]:
        """
        Show the menu and block until the user makes a choice.

        Returns:
            (width, height, entry, exit, seed)  - user confirmed
            None                                - user pressed ESC / quit
        """
        clock = pygame.time.Clock()

        # track sub-menu state here so __init__ stays clean
        self.in_custom_menu = False

        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return None
                if event.type == pygame.KEYDOWN:
                    if self.in_custom_menu:
                        self._handle_custom_menu_keys(event)
                    else:
                        self._handle_main_menu_keys(event)

            self._draw_background_maze()

            if self.in_custom_menu:
                self._draw_custom_panel()
            else:
                self._draw_main_panel()

            pygame.display.flip()
            clock.tick(60)

        return self.result