from typing import Tuple, Set, TypedDict, List, Optional, Dict  # NEW: Optional/Dict for ChallengeRenderer typing
import random
from maze import Maze, HuntAndKillGenerator, Cell, add_42_pattern
from path_finder import PathFinder
import pygame
import os


class Palette(TypedDict):
    """
    Represent a color palette for rendering elements.
    """
    name: str
    bg:       Tuple[int, int, int]
    wall:     Tuple[int, int, int]
    entry:    Tuple[int, int, int]
    exit:     Tuple[int, int, int]
    path:     Tuple[int, int, int]
    pattern:  Tuple[int, int, int]
    interior: Tuple[int, int, int]


PALETTES = [
    {
        "name":     "Moonlit Paper",
        "bg":       (46, 52, 64),
        "wall":     (28, 28, 46),
        "entry":    (45, 122, 58),
        "exit":     (107, 47, 160),
        "path":     (34, 85, 221),
        "pattern":  (192, 57, 27),
        "interior": (240, 236, 226),
    },
    {
        "name":     "Tokyo Night",
        "bg":       (26, 27, 46),
        "wall":     (195, 199, 232),
        "entry":    (57, 255, 20),
        "exit":     (255, 107, 53),
        "path":     (0, 212, 255),
        "pattern":  (255, 45, 120),
        "interior": (26, 27, 46),
    },
    {
        "name":     "Synthwave Sunset",
        "bg":       (22, 0, 30),
        "wall":     (212, 184, 224),
        "entry":    (0, 255, 225),
        "exit":     (255, 0, 170),
        "path":     (249, 240, 2),
        "pattern":  (255, 79, 88),
        "interior": (22, 0, 30),
    },
    {
        "name":     "Nordic Forest",
        "bg":       (46, 52, 64),
        "wall":     (236, 239, 244),
        "entry":    (235, 203, 139),
        "exit":     (191, 97, 106),
        "path":     (163, 190, 140),
        "pattern":  (136, 192, 208),
        "interior": (46, 52, 64),
    },
]


class Renderer:
    """
    Handles graphical rendering and interactive display of a maze.

    Provides a visual interface for drawing the maze, solution path,
    and UI panels using pygame. Supports keyboard controls for
    interaction and regeneration.

    Attributes:
    maze (Maze): Maze structure to render.
    path (Tuple[List[Cell], List[str]]): Computed path and directions.
    entry (Tuple[int, int]): Entry coordinates.
    exit (Tuple[int, int]): Exit coordinates.
    canvas (pygame.Surface): Main maze drawing surface.
    info_canvas (pygame.Surface): UI information panel surface.
    window_width (int): Width of rendering window.
    window_height (int): Height of rendering window.
    info_width (int): Width of side information panel.
    cell_length (int): Pixel size of each maze cell.
    stroke_length (int): Thickness of maze walls.
    palette_index (int): Index of active color palette.
    panel_cursor (int): Which panel menu item is highlighted.
    show_path (bool): Whether solution path is displayed.
    back_to_menu (bool): True when user pressed Back to return to menu.
    """

    def __init__(self,
                 maze: Maze,
                 path: Tuple[List[Cell], List[str]],
                 entry: Tuple[int, int],
                 exit: Tuple[int, int],
                 screen: pygame.Surface,
                 randomize_on_regen: bool = False) -> None:
        """Initialize the renderer."""
        self.maze  = maze
        self.path  = path
        self.entry = entry
        self.exit  = exit
        self.randomize_on_regen = randomize_on_regen

        self.window_width, self.window_height = screen.get_size()
        self.info_width  = 300
        self.min_padding = 20

        # animation state
        self.animate_path    = False   # toggle animation on/off
        self.animation_index = 0       # current step in path
        self.animation_timer = 0       # time accumulator (ms)
        self.animation_delay = 300     # ms between steps (lower = faster)

        self.screen = screen

        _HERE = os.path.dirname(os.path.abspath(__file__))
        _candidates = [
            os.path.join(_HERE, "DejaVuSans.ttf"),
            os.path.join(_HERE, "dejavu-sans", "DejaVuSans.ttf"),
        ]
        def _load_font(size: int) -> pygame.font.Font:
            for path in _candidates:
                if os.path.isfile(path):
                    return pygame.font.Font(path, size)
            return pygame.font.SysFont(None, size)

        self.font       = _load_font(20)
        self.font_opt   = _load_font(22)
        self.font_title = _load_font(26)

        self._path_dir_out:  dict = {}   # cell → direction leaving it
        self._path_dir_in:   dict = {}   # cell → direction arriving into it
        self._rebuild_path_index()

        self.clock = pygame.time.Clock()

        # drawing surfaces
        self.maze_area_width  = self.window_width - self.info_width
        self.maze_area_height = self.window_height
        self.canvas      = pygame.Surface((self.maze_area_width,
                                           self.maze_area_height))
        self.info_canvas = pygame.Surface((self.info_width,
                                           self.window_height))

        self._recalculate_geometry()

        self.palette_index = 0
        self._apply_palette()

        self.show_path = True
        self.running   = True

        self.panel_cursor = 0      # highlighted item in the right-side menu
        self.back_to_menu = False  # True = ESC/Back pressed → return to menu

    # animation helpers

    def _get_path_positions_list(self) -> List[Tuple[int, int]]:
        return [(cell.x, cell.y) for cell in self.path[0]]


    def _rebuild_path_index(self) -> None:
        self._path_dir_out = {}
        self._path_dir_in  = {}
        cells, dirs = self.path
        for i, cell in enumerate(cells):
            if i < len(dirs):
                self._path_dir_out[cell] = dirs[i]
            if i > 0:
                self._path_dir_in[cell] = dirs[i - 1]

    def _update_animation(self, dt: int) -> None:
        """
        Advance path animation by one step when enough time has passed.
        dt = milliseconds since last frame.
        """
        if not self.animate_path:
            return

        self.animation_timer += dt

        if self.animation_timer >= self.animation_delay:
            self.animation_timer = 0
            if self.animation_index < len(self.path[0]) - 1:
                self.animation_index += 1
            if self.animation_index >= len(self.path[0]) - 1:
                self.animate_path = False

    # palette

    def _apply_palette(self) -> None:
        """Apply the currently selected colour palette."""
        p = PALETTES[self.palette_index]
        self.bg_colour      = p["bg"]
        self.wall_colour    = p["wall"]
        self.entry_colour   = p["entry"]
        self.exit_colour    = p["exit"]
        self.path_colour    = p["path"]
        self.protect_colour = p["pattern"]
        self.interior_colour = p["interior"]
        self.keyword_colour = (255, 255, 0)    # yellow – selected item
        self.text_colour    = (255, 255, 255)  # white  – normal text

    def _cycle_palette(self) -> None:
        """Advance to the next colour palette, wrapping around."""
        self.palette_index = (self.palette_index + 1) % len(PALETTES)
        self._apply_palette()

    # ── panel menu ────────────────────────────────────────────────────────

    # Each tuple: (display label, shortcut hint shown on right, method name)
    PANEL_OPTIONS = [
        ("Regenerate",     "R",   "_action_regenerate"),
        ("Show/hide path", "P",   "_action_toggle_path"),
        ("Change colour",  "C",   "_action_cycle_colour"),
        ("Animate",        "A",   "_action_animate"),
        ("Speed  +",       "+",   "_action_speed_up"),
        ("Speed  -",       "-",   "_action_speed_down"),
        ("Back",           "ESC", "_action_back"),
    ]

    def _draw_panel_option(self, y: int, index: int,
                           label: str, key_hint: str) -> int:
        """
        Draw one selectable option line onto info_canvas.
        Arrow + yellow colour when selected.
        Returns new y position below the line.
        """
        x        = 20
        selected = (index == self.panel_cursor)
        arrow    = "▶  " if selected else "    "
        color    = self.keyword_colour if selected else self.text_colour

        line_surf = self.font_opt.render(arrow + label, True, color)
        self.info_canvas.blit(line_surf, (x, y))

        # shortcut key hint, right-aligned
        hint_col  = self.keyword_colour if selected else (160, 160, 180)
        hint_surf = self.font.render(f"[{key_hint}]", True, hint_col)
        hx = self.info_width - hint_surf.get_width() - 8
        self.info_canvas.blit(hint_surf, (hx, y + 2))

        return y + line_surf.get_height() + 6

    def _draw_colour_panel(self) -> None:
        """
        Render the right-side panel as a navigable menu.
        Navigate with UP/DOWN + ENTER, or press shortcut keys directly.
        """
        mx = 20   # left margin
        self.info_canvas.fill(self.bg_colour)

        # palette name
        y = 20
        name_surf = self.font_title.render(
            PALETTES[self.palette_index]["name"], True, self.text_colour)
        self.info_canvas.blit(name_surf, (mx, y))
        y += name_surf.get_height() + 8

        # palette indicator dots
        dot_w = (self.info_width - 2 * mx) // len(PALETTES)
        for i in range(len(PALETTES)):
            dot_col = (255, 255, 255) if i == self.palette_index \
                      else (85, 85, 102)
            pygame.draw.rect(self.info_canvas, dot_col,
                             (mx + i * dot_w, y, dot_w - 2, 5))
        y += 14

        pygame.draw.line(self.info_canvas, (60, 60, 80),
                         (mx, y), (self.info_width - mx, y), 1)
        y += 10

        # navigable option list
        for i, (label, key_hint, _) in enumerate(self.PANEL_OPTIONS):
            y = self._draw_panel_option(y, i, label, key_hint)

        self.screen.blit(self.info_canvas, (self.maze_area_width, 0))

    def _action_toggle_path(self) -> None:
        """Show or hide the solution path."""
        self.show_path = not self.show_path

    def _action_cycle_colour(self) -> None:
        """Advance to the next colour palette."""
        self._cycle_palette()

    def _action_animate(self) -> None:
        """Start (or restart) path animation from the beginning."""
        self.animate_path    = True
        self.show_path       = True
        self.animation_index = 0
        self.animation_timer = 0

    def _action_speed_up(self) -> None:
        """Decrease animation delay → faster playback."""
        self.animation_delay = max(50, self.animation_delay - 50)

    def _action_speed_down(self) -> None:
        """Increase animation delay → slower playback."""
        self.animation_delay = min(1000, self.animation_delay + 50)

    def _action_back(self) -> None:
        """Return to the menu."""
        self.back_to_menu = True
        self.running      = False

    # event handling

    def _handle_events(self) -> None:
        """
        Process all pending pygame events.

        Two ways to trigger any panel action:
          1. Press its shortcut key directly (R, P, C, A, +, -, ESC).
          2. Navigate with UP/DOWN arrows then press ENTER.
        """
        # shortcut key → action method mapping
        shortcut_map = {
            pygame.K_r:      self._action_regenerate,
            pygame.K_p:      self._action_toggle_path,
            pygame.K_c:      self._action_cycle_colour,
            pygame.K_a:      self._action_animate,
            pygame.K_EQUALS: self._action_speed_up,
            pygame.K_MINUS:  self._action_speed_down,
            pygame.K_ESCAPE: self._action_back,
        }

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:

                if event.key == pygame.K_UP:
                    # move cursor up in the panel menu, wrap around
                    self.panel_cursor = (
                        self.panel_cursor - 1) % len(self.PANEL_OPTIONS)

                elif event.key == pygame.K_DOWN:
                    # move cursor down in the panel menu, wrap around
                    self.panel_cursor = (
                        self.panel_cursor + 1) % len(self.PANEL_OPTIONS)

                elif event.key == pygame.K_RETURN:
                    # activate the currently highlighted panel option
                    _, _, method_name = self.PANEL_OPTIONS[self.panel_cursor]
                    getattr(self, method_name)()

                elif event.key in shortcut_map:
                    # shortcut keys work regardless of cursor position
                    shortcut_map[event.key]()

    # colour helpers

    def _get_interior_colour(
            self,
            cur_position: Tuple[int, int],
            path_positions: Set[Tuple[int, int]]
    ) -> Tuple[int, int, int]:
        """
        Return the fill colour for a cell's interior.

        Priority: entry > exit > path (if visible) > pattern > normal.
        """
        cell = self.maze.get_cell(*cur_position)

        if cur_position == self.entry:
            return self.entry_colour
        elif cur_position == self.exit:
            return self.exit_colour
        elif cur_position in path_positions and self.show_path:
            return self.path_colour
        elif cell and cell.is_pattern:
            return self.protect_colour
        else:
            return self.interior_colour

    def _get_wall_colour(self, cell: Cell,
                         direction: str) -> Tuple[int, int, int]:
        """
        Return the colour for one wall segment of a cell.

        During animation, walls are plain wall/interior colour (no path
        highlight on walls — the dot marker is used instead).
        When path is shown statically, walls along the path are coloured.
        """
        if self.animate_path:
            return self.wall_colour if cell.walls[direction] \
                   else self.interior_colour

        if self.show_path:
            out_dir = self._path_dir_out.get(cell)
            if out_dir and (cell.x, cell.y) != self.exit and direction == out_dir:
                return self.path_colour

            in_dir = self._path_dir_in.get(cell)
            if in_dir and (cell.x, cell.y) != self.entry:
                if in_dir == "S" and direction == "N":
                    return self.path_colour
                if in_dir == "E" and direction == "W":
                    return self.path_colour

        return self.wall_colour if cell.walls[direction] \
               else self.interior_colour


    # drawing primitives
    def _draw_rectangle(self,
                        surface: pygame.Surface,
                        colour: Tuple[int, int, int],
                        x: int, y: int,
                        width: int, height: int) -> None:
        pygame.draw.rect(surface, colour, (x, y, width, height))

    def _draw_interior_of_cell(self,
                                surface: pygame.Surface,
                                colour: Tuple[int, int, int],
                                x0: int, y0: int) -> None:
        """Fill the interior square of a cell (inside the walls)."""
        s = self.stroke_length
        self._draw_rectangle(
            surface, colour,
            x0 + s, y0 + s,
            self.cell_length - 2 * s,
            self.cell_length - 2 * s,
        )

    def _draw_side_of_cell(self,
                            surface: pygame.Surface,
                            colour: Tuple[int, int, int],
                            direction: str,
                            x0: int, y0: int) -> None:
        """
        Draw one wall segment (or corner) of a cell.
        direction is one of: N, NE, E, SE, S, SW, W, NW.
        """
        s  = self.stroke_length
        cl = self.cell_length

        if direction == "N":
            self._draw_rectangle(surface, colour,
                                 x0 + s, y0, cl - 2 * s, s)
        elif direction == "NE":
            self._draw_rectangle(surface, colour,
                                 x0 + cl - s, y0, s, s)
        elif direction == "E":
            self._draw_rectangle(surface, colour,
                                 x0 + cl - s, y0 + s, s, cl - 2 * s)
        elif direction == "SE":
            self._draw_rectangle(surface, colour,
                                 x0 + cl - s, y0 + cl - s, s, s)
        elif direction == "S":
            self._draw_rectangle(surface, colour,
                                 x0 + s, y0 + cl - s, cl - 2 * s, s)
        elif direction == "SW":
            self._draw_rectangle(surface, colour,
                                 x0, y0 + cl - s, s, s)
        elif direction == "W":
            self._draw_rectangle(surface, colour,
                                 x0, y0 + s, s, cl - 2 * s)
        elif direction == "NW":
            self._draw_rectangle(surface, colour,
                                 x0, y0, s, s)

    # full frame render

    def _render(self, draw_panel: bool = True) -> None:
        """
        Draw one complete frame: maze on the left, panel on the right.

        Args:
            draw_panel: when False the right-side info panel is skipped.
                        The menu sets this to False so its own panel
                        is the only thing drawn on the right side.
        """
        # which cells to colour as "path" this frame
        if self.animate_path:
            partial = self._get_path_positions_list()[:self.animation_index + 1]
            path_positions = set(partial)
        else:
            path_positions = {(c.x, c.y) for c in self.path[0]}

        step = self.cell_length - self.stroke_length
        self.canvas.fill(self.bg_colour)

        for row in range(self.maze.height):
            y0 = row * step + self.padding_y_side
            for col in range(self.maze.width):
                x0   = col * step + self.padding_x_side
                cell = self.maze.get_cell(col, row)

                # corners are always wall colour
                for corner in ["NE", "SE", "SW", "NW"]:
                    self._draw_side_of_cell(self.canvas, self.wall_colour,
                                            corner, x0, y0)

                # four cardinal walls
                if cell:
                    for direction in cell.walls:
                        self._draw_side_of_cell(
                            self.canvas,
                            self._get_wall_colour(cell, direction),
                            direction, x0, y0,
                        )

                # cell interior
                self._draw_interior_of_cell(
                    self.canvas,
                    self._get_interior_colour((col, row), path_positions),
                    x0, y0,
                )

        # animation: draw a dot at the current path position
        if self.animate_path and self.path[0]:
            cur = self.path[0][self.animation_index]
            cx  = cur.x * step + self.padding_x_side + self.cell_length // 2
            cy  = cur.y * step + self.padding_y_side + self.cell_length // 2
            pygame.draw.circle(self.canvas, self.protect_colour,
                               (cx, cy), self.cell_length // 6)

        self.screen.blit(self.canvas, (0, 0))
        if draw_panel:
            self._draw_colour_panel()

    def _safe_random_cell(self, test_maze: Maze, w: int, h: int) -> Tuple[int, int]:
        """
        pick a random (x, y) inside the maze that is not on the
        42 pattern. Re-rolls until it finds a free cell — same approach
        menu.py uses for the initial Random Maze entry/exit picks.
        """
        while True:
            x = random.randint(0, w - 1)
            y = random.randint(0, h - 1)
            cell = test_maze.get_cell(x, y)
            if cell is not None and not cell.is_pattern:
                return x, y

    def _action_regenerate(self) -> None:
        """
        Regenerate the maze with a new random seed.

        If randomize_on_regen is True (Random Maze), width, height, entry
        and exit are all re-rolled too, just like picking "Random Maze"
        fresh from the main menu. Otherwise (Custom Maze / background),
        only the seed changes and width/height/entry/exit stay fixed.

        Animation is reset so pressing R during animation restarts it.
        """
        seed = random.randint(1, 10000)

        # randomize width/height/entry/exit too when requested.
        if self.randomize_on_regen:
            width  = random.randint(10, 100)
            height = random.randint(10, 100)

            test_maze = Maze(width, height)
            add_42_pattern(test_maze)
            entry = self._safe_random_cell(test_maze, width, height)
            exit_ = self._safe_random_cell(test_maze, width, height)
            while exit_ == entry:
                exit_ = self._safe_random_cell(test_maze, width, height)

            self.entry = entry
            self.exit  = exit_
            self.maze  = Maze(width, height)
        else:
            self.maze = Maze(self.maze.width, self.maze.height)  # old behavior kept

        add_42_pattern(self.maze)
        HuntAndKillGenerator(seed).generate(self.maze)
        entry_cell = self.maze.get_cell(*self.entry)
        exit_cell  = self.maze.get_cell(*self.exit)
        self.path  = PathFinder(self.maze).find_path(entry_cell, exit_cell)

        self._rebuild_path_index()
        self.animate_path    = False
        self.animation_index = 0
        self.animation_timer = 0

        self._recalculate_geometry()

    def _recalculate_geometry(self) -> None:
        """
        # recompute cell_length, stroke_length and padding for the
        # current self.maze size. Mirrors the geometry block that used
        # to live inline in __init__, factored out so _action_regenerate
        # can call it again after width/height change.
        """
        available_w = self.maze_area_width  - 2 * self.min_padding
        available_h = self.maze_area_height - 2 * self.min_padding

        step_w = (available_w * 9) // (9 * self.maze.width  + 1)
        step_h = (available_h * 9) // (9 * self.maze.height + 1)
        step = min(step_w, step_h)

        self.stroke_length = max(1, step // 3)
        self.cell_length   = step + self.stroke_length
        real_width  = self.maze.width  * step + self.stroke_length
        real_height = self.maze.height * step + self.stroke_length
        self.padding_x_side = (self.maze_area_width  - real_width)  // 2
        self.padding_y_side = (self.maze_area_height - real_height) // 2
    # ── main loop ────────────────────────────────────────────────────────

    def run(self) -> bool:
        """
        Run the maze display loop until the user leaves.

        Returns:
            True  - user pressed Back/ESC  → caller should return to menu.
            False - user closed the window → caller should quit..
        """
        self._render()
        pygame.display.flip()

        while self.running:
            self._handle_events()
            dt = self.clock.tick(60)
            self._update_animation(dt)
            self._render()
            pygame.display.flip()

        return self.back_to_menu


class ChallengeRenderer:  # NEW: fully rewritten

    """
    Two-player race mode — three levels with escalating mechanics.

    All levels share:
      * Fast animated thin-LINE path reveal (not filled squares).
      * Fading 5-cell trace per player, offset left / right of center.
      * Split-circle avatar when both players share a cell.
      * P1 soft-purple / P2 warm-gold, readable on every palette.

    Level 1 (Nordic Forest):    plain race after memorizing the path.
    Level 2 (Synthwave Sunset): collectables dropped every 12th step.
    Level 3 (Tokyo Night):      chaser follows path; reach exit first.
    """

    # NEW: level -> maze size
    LEVEL_SIZES = {
        1: (20, 20),
        2: (30, 30),
        3: (40, 40),
    }

    # NEW: which PALETTES[] entry each level uses
    LEVEL_PALETTE = {
        1: 3,   # "Nordic Forest"
        2: 2,   # "Synthwave Sunset"
        3: 1,   # "Tokyo Night"
    }

    # NEW: path-reveal line speed (ms per step) — fast flash
    REVEAL_LINE_DELAY_MS = 18

    # NEW: pause after line completes before hiding
    REVEAL_HOLD_MS = 600

    # NEW: player colours readable on all four palettes
    P1_COLOUR = (180, 100, 220)   # soft purple
    P2_COLOUR = (220, 175,  30)   # warm gold

    # NEW: fading trace settings
    TRACE_LEN    = 5    # cells kept in trail
    TRACE_OFFSET = 4    # px left/right offset from cell center

    def __init__(self,
                 maze: Maze,
                 entry: Tuple[int, int],
                 exit: Tuple[int, int],
                 path: Tuple[List[Cell], List[str]],
                 level: int,
                 screen: pygame.Surface) -> None:

        self.maze   = maze
        self.entry  = entry
        self.exit   = exit
        self.path   = path
        self.level  = level
        self.screen = screen

        self.window_width, self.window_height = screen.get_size()
        self.info_width       = 300
        self.min_padding      = 20
        self.maze_area_width  = self.window_width  - self.info_width
        self.maze_area_height = self.window_height

        self.canvas      = pygame.Surface((self.maze_area_width,
                                           self.maze_area_height))
        self.info_canvas = pygame.Surface((self.info_width,
                                           self.window_height))

        _HERE = os.path.dirname(os.path.abspath(__file__))
        _candidates = [
            os.path.join(_HERE, "DejaVuSans.ttf"),
            os.path.join(_HERE, "dejavu-sans", "DejaVuSans.ttf"),
        ]
        def _load_font(size: int) -> pygame.font.Font:
            for fpath in _candidates:
                if os.path.isfile(fpath):
                    return pygame.font.Font(fpath, size)
            return pygame.font.SysFont(None, size)

        self.font       = _load_font(20)
        self.font_big   = _load_font(40)
        self.font_title = _load_font(28)

        # NEW: pick palette by level
        p = PALETTES[self.LEVEL_PALETTE.get(level, 0)]
        self.bg_colour       = p["bg"]
        self.wall_colour     = p["wall"]
        self.entry_colour    = p["entry"]
        self.exit_colour     = p["exit"]
        self.path_colour     = p["path"]
        self.protect_colour  = p["pattern"]
        self.interior_colour = p["interior"]
        self.text_colour     = (255, 255, 255)
        self.p1_colour       = self.P1_COLOUR
        self.p2_colour       = self.P2_COLOUR

        self._recalculate_geometry()

        # player state
        self.p1_pos = entry
        self.p2_pos = entry
        # NEW: traces — list of last TRACE_LEN positions before current
        self.p1_trace: List[Tuple[int, int]] = []
        self.p2_trace: List[Tuple[int, int]] = []

        # NEW: path-reveal animation (thin animated line, not filled cells)
        self.reveal_line_index = 0    # how far along the line is drawn
        self.reveal_line_timer = 0    # ms accumulator
        self.reveal_hold_timer = 0    # ms spent in post-line hold
        self.reveal_done       = False

        # race state
        self.race_started   = False
        self.elapsed_ms     = 0
        self.winner: Optional[str] = None
        self.winner_time_ms = 0

        # Level 2 collectables
        # Every 12th path cell becomes a collectable triangle.
        # They are added progressively as the reveal line passes them.
        self.collectables: set = set()
        self.p1_collected = 0
        self.p2_collected = 0

        # NEW: Level 3 chaser
        # Walks the solution path after reveal; reaches exit -> both lose.
        self.chaser_index = 0
        self.chaser_timer = 0
        path_len = max(1, len(self.path[0]))
        # target crossing time: ~30 seconds (adjusts with path length)
        self.chaser_delay_ms = max(80, 30_000 // path_len)

        self.running = True
        self.result: Optional[str] = None
        self.clock   = pygame.time.Clock()

    # ------------------------------------------------------------------ geometry

    def _recalculate_geometry(self) -> None:
        available_w = self.maze_area_width  - 2 * self.min_padding
        available_h = self.maze_area_height - 2 * self.min_padding
        step_w = (available_w * 9) // (9 * self.maze.width  + 1)
        step_h = (available_h * 9) // (9 * self.maze.height + 1)
        step   = min(step_w, step_h)
        self.stroke_length  = max(1, step // 3)
        self.cell_length    = step + self.stroke_length
        real_w  = self.maze.width  * step + self.stroke_length
        real_h  = self.maze.height * step + self.stroke_length
        self.padding_x_side = (self.maze_area_width  - real_w)  // 2
        self.padding_y_side = (self.maze_area_height - real_h) // 2

    # ------------------------------------------------------------------ helpers

    def _cell_center(self, x: int, y: int) -> Tuple[int, int]:
        """Pixel center of maze cell (x, y)."""
        step = self.cell_length - self.stroke_length
        return (x * step + self.padding_x_side + self.cell_length // 2,
                y * step + self.padding_y_side + self.cell_length // 2)

    def _cell_top_left(self, x: int, y: int) -> Tuple[int, int]:
        step = self.cell_length - self.stroke_length
        return (x * step + self.padding_x_side,
                y * step + self.padding_y_side)

    @staticmethod
    def _dim(colour: Tuple[int, int, int], alpha: int) -> Tuple[int, int, int]:
        """NEW: Darken colour by alpha (255 = full, 0 = black). No Surface needed."""
        a = alpha / 255.0
        return (int(colour[0] * a), int(colour[1] * a), int(colour[2] * a))

    # ------------------------------------------------------------------ movement

    def _try_move(self, pos: Tuple[int, int], direction: str) -> Tuple[int, int]:
        cell = self.maze.get_cell(*pos)
        if cell is None or cell.walls[direction]:
            return pos
        dx, dy = {"N": (0,-1), "S": (0,1), "E": (1,0), "W": (-1,0)}[direction]
        return (pos[0] + dx, pos[1] + dy)

    def _push_trace(self, trace: List, pos: Tuple[int, int]) -> List:
        """NEW: Append pos, keep only last TRACE_LEN entries."""
        return (trace + [pos])[-self.TRACE_LEN:]

    def _collect(self) -> None:
        """NEW: Remove any collectables under either player."""
        if self.p1_pos in self.collectables:
            self.collectables.discard(self.p1_pos)
            self.p1_collected += 1
        if self.p2_pos in self.collectables:
            self.collectables.discard(self.p2_pos)
            self.p2_collected += 1

    # ------------------------------------------------------------------ events

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                self.result  = "menu"

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                    self.result  = "menu"
                    continue

                if self.winner is not None:
                    if event.key == pygame.K_RETURN:
                        self.running = False
                        self.result  = "next_level"
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
                    if self.level == 2:
                        self._collect()
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

    # ------------------------------------------------------------------ update

    def _update(self, dt_ms: int) -> None:
        if not self.reveal_done:
            self._update_reveal(dt_ms)
            return

        if self.winner is None:
            self.elapsed_ms += dt_ms

        # NEW: Level 3 — advance chaser along the path
        if self.level == 3 and self.winner is None:
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

    def _update_reveal(self, dt_ms: int) -> None:
        """NEW: Grow the animated path line step by step, then hold briefly."""
        path_len = len(self.path[0])
        if self.reveal_line_index < path_len - 1:
            self.reveal_line_timer += dt_ms
            steps = self.reveal_line_timer // self.REVEAL_LINE_DELAY_MS
            if steps:
                self.reveal_line_timer %= self.REVEAL_LINE_DELAY_MS
                self.reveal_line_index = min(
                    self.reveal_line_index + steps, path_len - 1)
                # NEW: Level 2 — drop collectables as head of line passes them
                if self.level == 2:
                    for i, cell in enumerate(self.path[0]):
                        if i > 0 and i % 12 == 0 and i <= self.reveal_line_index:
                            self.collectables.add((cell.x, cell.y))
        else:
            # line finished — wait REVEAL_HOLD_MS then start the race
            self.reveal_hold_timer += dt_ms
            if self.reveal_hold_timer >= self.REVEAL_HOLD_MS:
                self.reveal_done  = True
                self.race_started = True

    # ------------------------------------------------------------------ drawing

    def _draw_side_of_cell(self, surface: pygame.Surface,
                           colour: Tuple[int, int, int],
                           direction: str, x0: int, y0: int) -> None:
        s, cl = self.stroke_length, self.cell_length
        rects = {
            "N":  (x0+s,    y0,       cl-2*s, s),
            "NE": (x0+cl-s, y0,       s,      s),
            "E":  (x0+cl-s, y0+s,     s,      cl-2*s),
            "SE": (x0+cl-s, y0+cl-s,  s,      s),
            "S":  (x0+s,    y0+cl-s,  cl-2*s, s),
            "SW": (x0,      y0+cl-s,  s,      s),
            "W":  (x0,      y0+s,     s,      cl-2*s),
            "NW": (x0,      y0,       s,      s),
        }
        if direction in rects:
            pygame.draw.rect(surface, colour, rects[direction])

    def _draw_maze(self) -> None:
        """Draw walls and cell fills — no path colouring during race."""
        self.canvas.fill(self.bg_colour)
        for row in range(self.maze.height):
            for col in range(self.maze.width):
                x0, y0 = self._cell_top_left(col, row)
                cell   = self.maze.get_cell(col, row)
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
                    (x0+s, y0+s, self.cell_length-2*s, self.cell_length-2*s))

    def _draw_reveal_line(self) -> None:
        """NEW: Animated thin line growing from entry to current reveal head."""
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
        """NEW: Thin fading line following the player, offset left or right."""
        if len(trace) < 2:
            return
        n = len(trace)
        for i in range(n - 1):
            alpha = int(30 + 150 * (i + 1) / n)   # fades from old to new
            c  = self._dim(colour, alpha)
            p0 = (self._cell_center(*trace[i])[0]   + offset_x,
                  self._cell_center(*trace[i])[1])
            p1 = (self._cell_center(*trace[i+1])[0] + offset_x,
                  self._cell_center(*trace[i+1])[1])
            pygame.draw.line(self.canvas, c, p0, p1,
                             max(1, self.cell_length // 8))

    def _draw_collectables(self) -> None:
        """NEW: Small upward triangles at each collectable position (Level 2)."""
        r = max(3, self.cell_length // 5)
        for (cx, cy) in self.collectables:
            px, py = self._cell_center(cx, cy)
            tri = [(px, py - r), (px - r, py + r), (px + r, py + r)]
            pygame.draw.polygon(self.canvas, self.path_colour, tri)
            pygame.draw.polygon(self.canvas, (255, 255, 255), tri, 1)

    def _draw_chaser(self) -> None:
        """NEW: Pulsing red dot that walks the solution path (Level 3)."""
        if self.chaser_index >= len(self.path[0]):
            return
        cell = self.path[0][self.chaser_index]
        cx, cy = self._cell_center(cell.x, cell.y)
        r = max(3, self.cell_length // 3)
        # pulse brightness over 600 ms cycle
        pulse  = abs((self.elapsed_ms % 600) - 300) / 300.0
        bright = int(180 + 75 * pulse)
        pygame.draw.circle(self.canvas, (bright, 30, 30),  (cx, cy), r)
        pygame.draw.circle(self.canvas, (255, 80, 80), (cx, cy), max(1, r//2))

    def _draw_players(self) -> None:
        """NEW: Circles for both players; split half-half when on same cell."""
        import math
        r = max(3, self.cell_length // 3)

        if self.p1_pos == self.p2_pos:
            # NEW: vertically split circle — left=P1, right=P2
            cx, cy = self._cell_center(*self.p1_pos)
            # left half polygon (P1)
            left_pts = ([(cx, cy - r)] +
                        [(cx + int(r * math.cos(a)),
                          cy - int(r * math.sin(a)))
                         for a in [math.pi * i / 8 for i in range(8, 17)]] +
                        [(cx, cy + r)])
            # right half polygon (P2)
            right_pts = ([(cx, cy - r)] +
                         [(cx + int(r * math.cos(a)),
                           cy - int(r * math.sin(a)))
                          for a in [math.pi * i / 8 for i in range(0, 9)]] +
                         [(cx, cy + r)])
            pygame.draw.polygon(self.canvas, self.p1_colour, left_pts)
            pygame.draw.polygon(self.canvas, self.p2_colour, right_pts)
            # thin white dividing line and outline
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

        level_names = {1: "Nordic Forest", 2: "Synthwave", 3: "Tokyo Night"}
        title = self.font_title.render(
            f"Lvl {self.level} — {level_names.get(self.level, '')}", True,
            self.text_colour)
        self.info_canvas.blit(title, (x, y));  y += 46

        size_lbl = self.font.render(
            f"{self.maze.width} x {self.maze.height}", True, self.text_colour)
        self.info_canvas.blit(size_lbl, (x, y));  y += 34

        pygame.draw.line(self.info_canvas, (80, 80, 100),
                         (x, y), (self.info_width - x, y), 1);  y += 16

        # timer or reveal progress bar
        if not self.reveal_done:
            pct   = self.reveal_line_index / max(1, len(self.path[0]) - 1)
            bar_w = self.info_width - 2 * x
            pygame.draw.rect(self.info_canvas, (60, 60, 80),
                             (x, y, bar_w, 8))
            pygame.draw.rect(self.info_canvas, self.path_colour,
                             (x, y, int(bar_w * pct), 8))
            y += 20
            self.info_canvas.blit(
                self.font.render("Memorize the path!", True, self.path_colour),
                (x, y));  y += 30
        else:
            secs   = self.elapsed_ms / 1000.0
            t_surf = self.font_title.render(f"{secs:0.1f}s", True,
                                            self.text_colour)
            self.info_canvas.blit(t_surf, (x, y));  y += 46

        # player legend dots
        pygame.draw.circle(self.info_canvas, self.p1_colour, (x+8, y+10), 8)
        self.info_canvas.blit(
            self.font.render("P1  (arrows)", True, self.text_colour), (x+24, y))
        y += 30
        pygame.draw.circle(self.info_canvas, self.p2_colour, (x+8, y+10), 8)
        self.info_canvas.blit(
            self.font.render("P2  (WASD)", True, self.text_colour), (x+24, y))
        y += 36

        # NEW: Level 2 — collectable scoreboard
        if self.level == 2:
            pygame.draw.line(self.info_canvas, (80, 80, 100),
                             (x, y), (self.info_width - x, y), 1);  y += 12
            self.info_canvas.blit(
                self.font.render(f"P1 collected: {self.p1_collected}",
                                 True, self.p1_colour), (x, y));  y += 24
            self.info_canvas.blit(
                self.font.render(f"P2 collected: {self.p2_collected}",
                                 True, self.p2_colour), (x, y));  y += 24
            self.info_canvas.blit(
                self.font.render(f"Remaining: {len(self.collectables)}",
                                 True, self.text_colour), (x, y));  y += 28

        # NEW: Level 3 — chaser progress bar
        if self.level == 3 and self.reveal_done:
            pygame.draw.line(self.info_canvas, (80, 80, 100),
                             (x, y), (self.info_width - x, y), 1);  y += 12
            pct   = self.chaser_index / max(1, len(self.path[0]) - 1)
            bar_w = self.info_width - 2 * x
            pygame.draw.rect(self.info_canvas, (60, 30, 30),
                             (x, y, bar_w, 10))
            pygame.draw.rect(self.info_canvas, (220, 50, 50),
                             (x, y, int(bar_w * pct), 10))
            y += 14
            self.info_canvas.blit(
                self.font.render("Chaser progress", True, (220, 80, 80)),
                (x, y));  y += 26

        # winner / loss screen
        if self.winner is not None:
            pygame.draw.line(self.info_canvas, (80, 80, 100),
                             (x, y), (self.info_width - x, y), 1);  y += 14
            if self.winner == "Chaser":
                msg1, msg2, col = ("Chaser wins!",
                                   "Both players lose!", (220, 50, 50))
            else:
                msg1 = f"{self.winner} wins!"
                msg2 = f"Time: {self.winner_time_ms / 1000.0:0.1f}s"
                col  = (249, 240, 2)
            self.info_canvas.blit(
                self.font_title.render(msg1, True, col), (x, y));  y += 38
            self.info_canvas.blit(
                self.font.render(msg2, True, self.text_colour), (x, y));  y += 34
            self.info_canvas.blit(
                self.font.render("[ENTER] next level", True, (136, 192, 208)),
                (x, y));  y += 24
            self.info_canvas.blit(
                self.font.render("[ESC] menu", True, (136, 192, 208)), (x, y))

        self.screen.blit(self.info_canvas, (self.maze_area_width, 0))

    def _render(self) -> None:
        self._draw_maze()
        if not self.reveal_done:
            # NEW: during reveal phase, only show the animated line
            self._draw_reveal_line()
        else:
            # NEW: race phase — traces, then level extras, then avatars on top
            self._draw_trace(self.p1_trace, self.p1_colour, -self.TRACE_OFFSET)
            self._draw_trace(self.p2_trace, self.p2_colour,  self.TRACE_OFFSET)
            if self.level == 2:
                self._draw_collectables()
            if self.level == 3:
                self._draw_chaser()
            self._draw_players()
        self.screen.blit(self.canvas, (0, 0))
        self._draw_panel()

    # ------------------------------------------------------------------ main loop

    def run(self) -> Optional[str]:
        """
        Run the race until someone wins or chaser reaches exit (L3).

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