from typing import Tuple, Set, TypedDict, List
import random
from maze import Maze, HuntAndKillGenerator, Cell, add_42_pattern
from path_finder import PathFinder
from maze_utils import safe_random_cell  # NEW: shared helper, replaces local copy
from render_utils import load_font, recalculate_geometry  # NEW: shared helpers
import pygame
import os
# NOTE: ChallengeRenderer used to live in this file. It has moved to
# challenge/base.py (+ challenge/level1.py, level2.py, level3.py) so
# all challenge-mode code lives together and each level is its own
# small file. See challenge/runner.py for how it's launched now.


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

        # NEW: font loading moved to render_utils.load_font, shared with
        # ChallengeRenderer instead of each class having its own copy.
        _here = os.path.dirname(os.path.abspath(__file__))
        self.font       = load_font(20, _here)
        self.font_opt   = load_font(22, _here)
        self.font_title = load_font(26, _here)

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

    # NEW: _safe_random_cell removed from here — it's now the shared
    # maze_utils.safe_random_cell() function, used below in
    # _action_regenerate instead of a local copy.

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
            entry = safe_random_cell(test_maze, width, height)
            exit_ = safe_random_cell(test_maze, width, height)
            while exit_ == entry:
                exit_ = safe_random_cell(test_maze, width, height)

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
        Recompute cell_length, stroke_length and padding for the
        current self.maze size. Mirrors the geometry block that used
        to live inline in __init__, factored out so _action_regenerate
        can call it again after width/height change.

        NEW: the actual math now lives in render_utils.recalculate_geometry
        so Renderer and ChallengeRenderer share one implementation
        instead of each having their own copy.
        """
        (self.cell_length, self.stroke_length,
         self.padding_x_side, self.padding_y_side) = recalculate_geometry(
            self.maze_area_width, self.maze_area_height,
            self.maze.width, self.maze.height, self.min_padding,
        )
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