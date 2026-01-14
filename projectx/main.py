from __future__ import annotations

import json, pygame, math, os, random, sys, hashlib, asyncio
import numpy as np
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple, Any

FPS_TARGET = 144
DATA_FILE = "data.json"
TURN_DATA_PATH = "turn_data.json"
DOORS_FILE = "doors.json"
KEYS_PATH = "keys.json"

DEFAULT_WINDOW_W = 1920
DEFAULT_WINDOW_H = 1080

TILE = 32
PLAYER_HITBOX_WIDTH = 32
PLAYER_HITBOX_HEIGHT = 60
PLAYER_SIZE = (64, 64)
GRAVITY = 900.0
H_SPEED = 760.0
JUMP_V = -383.0

DASH_COOLDOWN = 2.0
DASH_PARTICLES = 30
WALK_PARTICLES = max(1, DASH_PARTICLES // 3)

BG_PATH = "bg.png"

SPAWN_TILE_ID = 100
KEY_TILE_ID = 67
COLLECTABLE_TILE_IDS = {8}
DOOR_TILE_IDS = {55, 65}
DOOR_OPEN_MAP: Dict[int, int] = {55: 54, 65: 85}

DEADLY_TILES = {82, 86, 88, 55, 56}

TILE_HITBOXES: Dict[int, Tuple[int, int, int, int]] = {
    86: (12, 20, 4, 8),
    88: (14, 0, 2, 32),
    83: (0, 0, 0, 0),
    76: (0, 20, 32, 12),
    54: (0, 0, 0, 0),
    85: (0, 0, 0, 0),
    91: (0, 0, 0, 0),
    92: (0, 0, 0, 0),
    93: (0, 0, 0, 0),
    94: (0, 0, 0, 0),
    95: (0, 0, 0, 0),
    96: (0, 0, 0, 0),
    97: (0, 0, 0, 0),
    98: (0, 0, 0, 0),
}
TILES_WITH_CUSTOM_HITBOX = set(TILE_HITBOXES.keys())

ONE_WAY_IDS = {2, 3, 4, 5}

PALETTE_COLS = 6
PALETTE_PADDING = 8

pygame.init()
pygame.mixer.init()
pygame.display.set_caption("Akif Clicker v1.0")
coin_s = pygame.mixer.Sound(os.path.join("assets", "coin.ogg"))
dash_s = pygame.mixer.Sound(os.path.join("assets", "dash.ogg"))
key_s = pygame.mixer.Sound(os.path.join("assets", "key.ogg"))
die_s = pygame.mixer.Sound(os.path.join("assets", "die.ogg"))

try:
    SCREEN = pygame.display.set_mode((1920, 1080))
    W, H = 1920, 1080
except pygame.error:
    W, H = 1920, 1080
    SCREEN = pygame.display.set_mode((W, H))

clock = pygame.time.Clock()
ZOOM = 2.0

debug = False
editor = False
mouse_painting = False
selected_tile = 1

font = pygame.font.Font(None, 24)
bigfont = pygame.font.Font(None, 36)

last_changes: List[Tuple[int, int, int, int]] = []
redo_stack: List[Tuple[int, int, int, int]] = []

per_tile_rotations: Dict[int, int] = {}
cell_rotations: Dict[Tuple[int, int], int] = {}

DOORS_META: List[Dict[str, Any]] = []
KEYS_META: List[Dict[str, Any]] = []

doors: List["Door"] = []
door_id_map: Dict[str, int] = {}
coins: List["Collectable"] = []

score = 0

camx = 0
camy = 0

particles: List["Particle"] = []

DECORATION_IDS = set(TILES_WITH_CUSTOM_HITBOX)
DECORATION_IDS.add(SPAWN_TILE_ID)
DECORATION_IDS |= COLLECTABLE_TILE_IDS
DECORATION_IDS.add(KEY_TILE_ID)

def change_brightness(surface, amount):
    arr = pygame.surfarray.pixels3d(surface).astype(np.int16)
    alpha = pygame.surfarray.pixels_alpha(surface).copy()
    arr += amount
    np.clip(arr, 0, 255, out=arr)
    new = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    pygame.surfarray.blit_array(new, arr.astype(np.uint8))
    pygame.surfarray.pixels_alpha(new)[:, :] = alpha
    return new

def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

def load_json_or_default(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return default

def safe_write_json(path: str, data) -> bool:
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
        return True
    except Exception as e:
        return False

def load_turn_data() -> Tuple[Dict[int, int], Dict[Tuple[int, int], int]]:
    per = {}
    cell = {}
    if not os.path.exists(TURN_DATA_PATH):
        return per, cell
    try:
        with open(TURN_DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            raw = data.get("turneds", {})
            for k, v in raw.items():
                if isinstance(k, str) and "," in k:
                    try:
                        gx, gy = map(int, k.split(","))
                        cell[(gx, gy)] = int(v) % 360
                    except Exception:
                        continue
                else:
                    try:
                        tid = int(k)
                        per[tid] = int(v) % 360
                    except Exception:
                        continue
    except Exception as e:
        pass
    return per, cell

def save_turn_data():
    out = {}
    for tid, deg in per_tile_rotations.items():
        out[str(tid)] = deg
    for (gx, gy), deg in cell_rotations.items():
        out[f"{gx},{gy}"] = deg
    safe_write_json(TURN_DATA_PATH, {"turneds": out})

per_tile_rotations, cell_rotations = load_turn_data()

def rotate_rect_coords(x: float, y: float, w: float, h: float, degrees: int, tile_size: int) -> Tuple[float, float, float, float]:
    deg = degrees % 360
    if deg == 0:
        return x, y, w, h
    if deg == 90:
        nx = y
        ny = tile_size - w - x
        nw = h
        nh = w
        return nx, ny, nw, nh
    if deg == 180:
        nx = tile_size - w - x
        ny = tile_size - h - y
        return nx, ny, w, h
    if deg == 270:
        nx = tile_size - h - y
        ny = x
        nw = h
        nh = w
        return nx, ny, nw, nh
    return x, y, w, h

def get_tile_rotation(tile_id: int, gx: int, gy: int) -> int:
    r = cell_rotations.get((gx, gy))
    if r is None:
        r = per_tile_rotations.get(tile_id, 0)
    return r or 0

def rotate_one_way_tile(tile_code: int) -> int:
    rotation_map = {2: 3, 3: 4, 4: 5, 5: 2}
    if tile_code in rotation_map:
        return rotation_map[tile_code]
    ori = tile_code % 10
    base = tile_code - ori
    if ori in rotation_map:
        return base + rotation_map[ori]
    return tile_code

def get_tile_hitbox_rect(tile_id: int, grid_x: int, grid_y: int, tile_size: int) -> Optional[pygame.Rect]:
    if tile_id not in TILE_HITBOXES:
        return None
    bx, by, bw, bh = TILE_HITBOXES[tile_id]
    rot = get_tile_rotation(tile_id, grid_x, grid_y)
    rx, ry, rw, rh = rotate_rect_coords(bx, by, bw, bh, rot, tile_size)
    if rw <= 0 or rh <= 0:
        return None
    wx = grid_x * tile_size + rx
    wy = grid_y * tile_size + ry
    return pygame.Rect(int(wx), int(wy), int(rw), int(rh))

def load_tile_images(tile_size: int) -> Dict[int, Optional[pygame.Surface]]:
    images: Dict[int, Optional[pygame.Surface]] = {}
    folder = os.path.join("assets", "tiles")
    if not os.path.isdir(folder):
        for tid in [1, 86, 88, 83, 55, 65, 67, 54, 85]:
            surf = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
            color = (180, 180, 180) if tid == 1 else (200, 60, 60)
            images[tid] = surf
        images[0] = None
        return images

    for fname in sorted(os.listdir(folder)):
        if not (fname.startswith("tile") and fname.endswith(".png")):
            continue
        try:
            tid = int(fname[4:-4])
        except ValueError:
            continue
        path = os.path.join(folder, fname)
        try:
            img = pygame.image.load(path).convert_alpha()
            img = pygame.transform.scale(img, (tile_size, tile_size))
            images[tid] = img
        except Exception as e:
            pass
    images[0] = None
    return images

def load_player_frames(size: Tuple[int, int], count: int = 5) -> List[pygame.Surface]:
    frames = []
    for i in range(count):
        path = os.path.join("assets", f"idle_{i}.png")
        if os.path.isfile(path):
            try:
                img = pygame.image.load(path).convert_alpha()
                img = pygame.transform.scale(img, size)
                frames.append(img)
                continue
            except Exception:
                pass
        surf = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.rect(surf, (0, 0, 0), surf.get_rect(), 2)
        frames.append(surf)
    return frames

@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    color: Tuple[int, int, int]
    radius: int

    max_life: float = field(init=False)
    alive: bool = field(init=False, default=True)

    def __post_init__(self):
        self.max_life = float(self.life)

    def update(self, dt: float):
        if not self.alive:
            return
        self.life -= dt
        if self.life <= 0:
            self.alive = False
            return
        self.vy += 60.0 * dt
        self.x += self.vx * dt
        self.y += self.vy * dt

    def draw(self, surface: pygame.Surface, camx: int, camy: int):
        if not self.alive:
            return
        alpha = max(0, min(255, int(255 * (self.life / self.max_life))))
        size = self.radius * 2
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        col = (*self.color, alpha)
        pygame.draw.circle(surf, col, (self.radius, self.radius), self.radius)
        screen_x = int(self.x - camx - self.radius)
        screen_y = int(self.y - camy - self.radius)
        surface.blit(surf, (screen_x, screen_y))

def emit_particles(x: float, y: float, count: int, speed_spread: float = 30, life_spread: float = 0.6,
                   color: Tuple[int, int, int] = (200, 200, 200), radius_range: Tuple[int, int] = (2, 4)):
    if performance:
        for _ in range(count):
            speed = random.uniform(speed_spread * 0.5, speed_spread)
            vx = random.uniform(-1.0, 1.0) * speed * 0.6
            vy = -15 + random.uniform(-6, 6)
            life = random.uniform(0.25, max(0.3, life_spread))
            r = random.randint(radius_range[0], radius_range[1])
            p = Particle(x + random.uniform(-6, 6), y + random.uniform(-2, 2), vx, vy, life, color, r)
            particles.append(p)

class Collectable:
    def __init__(
        self,
        x: float,
        y: float,
        img: Optional[pygame.Surface],
        value: int = 1,
        bob_amplitude: float = 4.0,
        bob_speed: float = 3.0,
        on_collect: Optional[Callable] = None,
        sound: Optional[pygame.mixer.Sound] = None,
        respawn_time: Optional[float] = None
        ):
        self.x0 = float(x)
        self.y0 = float(y)
        self.img = img
        self.value = value

        self.w = img.get_width() if img else 0
        self.h = img.get_height() if img else 0

        self.bob_amplitude = bob_amplitude
        self.bob_speed = bob_speed
        self._time = random.uniform(0, 2 * math.pi)

        self.collected = False
        self.respawn_time = respawn_time
        self._respawn_timer = 0.0

        self.on_collect = on_collect
        self.sound = sound

        self.rect = pygame.Rect(int(self.x0 + self.w * 0.15), int(self.y0 + self.h * 0.15), int(self.w * 0.7), int(self.h * 0.7))

        self._draw_x = float(self.x0)
        self._draw_y = float(self.y0)

    @classmethod
    def from_tile_center(cls, gx: int, gy: int, tile_size: int, img: Optional[pygame.Surface], **kwargs):
        cx = gx * tile_size + tile_size // 2
        cy = gy * tile_size + tile_size // 2
        x = cx - (img.get_width() // 2) if img else gx * tile_size
        y = cy - (img.get_height() // 2) if img else gy * tile_size
        return cls(x, y, img, **kwargs)

    def update(self, dt: float):
        self._time += dt
        if self.collected:
            if self.respawn_time is not None:
                self._respawn_timer -= dt
                if self._respawn_timer <= 0.0:
                    self.collected = False
                    self._time = 0.0
        bob = math.sin(self._time * self.bob_speed) * self.bob_amplitude
        self._draw_x = self.x0
        self._draw_y = self.y0 + bob
        self.rect.x = int(self._draw_x + self.w * 0.15)
        self.rect.y = int(self._draw_y + self.h * 0.15)

    def draw(self, surface: pygame.Surface, camx: int = 0, camy: int = 0):
        if self.collected:
            return
        draw_x = getattr(self, "_draw_x", self.x0)
        draw_y = getattr(self, "_draw_y", self.y0)
        if not self.img:
            pygame.draw.circle(surface, (255, 220, 40), (int(draw_x - camx + self.w / 2), int(draw_y - camy + self.w / 2)), max(4, self.w // 3))
            return
        surface.blit(self.img, (int(draw_x - camx), int(draw_y - camy)))

    def check_collect(self, player_rect: pygame.Rect) -> bool:
        if self.collected:
            return False
        if player_rect.colliderect(self.rect):
            self._do_collect()
            return True
        return False

    def _do_collect(self):
        self.collected = True
        if self.sound:
            try:
                self.sound.play()
            except Exception:
                pass
        if self.on_collect:
            try:
                self.on_collect(self)
            except Exception:
                pass
        if self.respawn_time is not None:
            self._respawn_timer = self.respawn_time

    def force_respawn(self):
        self.collected = False
        self._respawn_timer = 0.0
        self._time = 0.0

    def is_visible(self) -> bool:
        return not self.collected

class Door:
    def __init__(self, cells: List[Tuple[int, int]], grid_ref: "Grid", door_id: str, original_tiles: Optional[List[int]] = None):
        self.id = str(door_id)
        self.cells = [tuple(c) for c in cells]
        self.grid = grid_ref
        if original_tiles and len(original_tiles) == len(self.cells):
            self._original_tiles = {tuple(c): int(t) for c, t in zip(self.cells, original_tiles)}
        else:
            self._original_tiles = {tuple(c): self.grid.get_tile(c[0], c[1]) for c in self.cells}
        self.opened = False

    def open(self):
        if self.opened:
            return
        for (gx, gy) in self.cells:
            old = self._original_tiles.get((gx, gy), self.grid.get_tile(gx, gy))
            new_tile = DOOR_OPEN_MAP.get(old, self.grid.get_tile(gx, gy))
            try:
                self.grid.set_tile(gx, gy, new_tile, record=False)
                self.grid._draw_cell(gx, gy)
            except Exception:
                pass
        self.opened = True

class Key(Collectable):
    def __init__(self, k_id, x, y, img, doors: Optional[List[Door]] = None, meta_idx: int = -1, **kwargs):
        self.doors = doors if doors is not None else []
        self.meta_idx = meta_idx
        super().__init__(x, y, img, **kwargs)
        self.is_key = True
        self.id = k_id

    @classmethod
    def from_tile_center(cls, gx, gy, tile_size, img, doors: Optional[List[Door]] = None, meta_idx: int = -1):
        cx = gx * tile_size + tile_size // 2
        cy = gy * tile_size + tile_size // 2
        x = cx - (img.get_width() // 2) if img else gx * tile_size
        y = cy - (img.get_height() // 2) if img else gy * tile_size
        return cls(x, y, img, doors or [], meta_idx, value=0, respawn_time=None)

    def _do_collect(self):
        for d in self.doors:
            try:
                d.open()
            except Exception:
                pass
        super()._do_collect()

class Grid:
    def __init__(self, tile_size: int, grid_data: List[List[int]], tile_images: Dict[int, Optional[pygame.Surface]]):
        self.tile = tile_size
        self.grid = grid_data
        self.rows = len(self.grid)
        self.cols = len(self.grid[0]) if self.rows > 0 else 0
        self.tile_images = tile_images
        self.world_surface = pygame.Surface((max(1, self.cols * self.tile), max(1, self.rows * self.tile)), pygame.SRCALPHA)
        self.decoration_surface = pygame.Surface((max(1, self.cols * self.tile), max(1, self.rows * self.tile)), pygame.SRCALPHA)
        self.update_surfaces()

    def update_surfaces(self):
        w = max(1, self.cols * self.tile)
        h = max(1, self.rows * self.tile)
        self.world_surface = pygame.Surface((w, h), pygame.SRCALPHA)
        self.decoration_surface = pygame.Surface((w, h), pygame.SRCALPHA)
        self.world_surface.fill((30, 30, 30))
        self.decoration_surface.fill((0, 0, 0, 0))
        for gy, row in enumerate(self.grid):
            for gx, _ in enumerate(row):
                self._draw_cell_raw(gx, gy)

    def _clear_cell(self, gx: int, gy: int):
        rect = pygame.Rect(gx * self.tile, gy * self.tile, self.tile, self.tile)
        self.world_surface.fill((30, 30, 30), rect)
        self.decoration_surface.fill((0, 0, 0, 0), rect)

    def _draw_image_with_rotation(self, surf: pygame.Surface, img: pygame.Surface, pos: Tuple[int, int], rotation_deg: int):
        if img is None:
            return
        rotation_deg = rotation_deg % 360
        if rotation_deg == 0:
            surf.blit(img, pos)
            return
        rotated = pygame.transform.rotate(img, rotation_deg)
        cx = pos[0] + self.tile // 2
        cy = pos[1] + self.tile // 2
        rect = rotated.get_rect(center=(cx, cy))
        surf.blit(rotated, rect.topleft)

    def _draw_cell_raw(self, gx: int, gy: int):
        val = self.grid[gy][gx]
        pos = (gx * self.tile, gy * self.tile)
        img = self.tile_images.get(val)
        rot = get_tile_rotation(val, gx, gy) or 0

        if val == 0:
            return
        if val in DECORATION_IDS:
            if val in COLLECTABLE_TILE_IDS:
                return
            if img:
                self._draw_image_with_rotation(self.decoration_surface, img, pos, rot)
            else:
                if val == SPAWN_TILE_ID:
                    tmp = pygame.Surface((self.tile, self.tile), pygame.SRCALPHA)
                    tmp.fill((0, 220, 0, 120))
                    self._draw_image_with_rotation(self.decoration_surface, tmp, pos, rot)
                    pygame.draw.rect(self.decoration_surface, (0, 150, 0), (pos[0], pos[1], self.tile, self.tile), 2)
                else:
                    tmp = pygame.Surface((self.tile, self.tile), pygame.SRCALPHA)
                    tmp.fill((160, 40, 40, 180))
                    self._draw_image_with_rotation(self.decoration_surface, tmp, pos, rot)
        else:
            if img:
                self._draw_image_with_rotation(self.world_surface, img, pos, rot)
            else:
                pygame.draw.rect(self.world_surface, (200, 200, 200), (pos[0], pos[1], self.tile, self.tile))

    def _draw_cell(self, gx: int, gy: int):
        self._clear_cell(gx, gy)
        val = self.grid[gy][gx]
        if val == 0:
            return
        pos = (gx * self.tile, gy * self.tile)
        img = self.tile_images.get(val)
        rot = get_tile_rotation(val, gx, gy) or 0

        if val in DECORATION_IDS:
            if val in COLLECTABLE_TILE_IDS:
                return
            if img:
                self._draw_image_with_rotation(self.decoration_surface, img, pos, rot)
            else:
                if val == SPAWN_TILE_ID:
                    tmp = pygame.Surface((self.tile, self.tile), pygame.SRCALPHA)
                    tmp.fill((0, 220, 0, 120))
                    self._draw_image_with_rotation(self.decoration_surface, tmp, pos, rot)
                    pygame.draw.rect(self.decoration_surface, (0, 150, 0), (pos[0], pos[1], self.tile, self.tile), 2)
                else:
                    tmp = pygame.Surface((self.tile, self.tile), pygame.SRCALPHA)
                    tmp.fill((160, 40, 40, 180))
                    self._draw_image_with_rotation(self.decoration_surface, tmp, pos, rot)
        else:
            if img:
                self._draw_image_with_rotation(self.world_surface, img, pos, rot)
            else:
                pygame.draw.rect(self.world_surface, (200, 200, 200), (pos[0], pos[1], self.tile, self.tile))

    def set_tile(self, gx: int, gy: int, tile_id: int, record: bool = True):
        global last_changes, redo_stack
        if not self.in_bounds(gx, gy):
            return
        old = self.grid[gy][gx]
        if old == tile_id:
            return
        self.grid[gy][gx] = tile_id
        if record:
            last_changes.append((gx, gy, old, tile_id))
            redo_stack.clear()
        self._draw_cell(gx, gy)

    def set_cell_rotation(self, gx: int, gy: int, deg: int, save: bool = True):
        if not self.in_bounds(gx, gy):
            return
        deg = int(deg) % 360
        if deg == 0:
            if (gx, gy) in cell_rotations:
                del cell_rotations[(gx, gy)]
        else:
            cell_rotations[(gx, gy)] = deg
        self._draw_cell(gx, gy)
        if save:
            save_turn_data()

    def toggle_cell_rotation(self, gx: int, gy: int, step: int = 90):
        if not self.in_bounds(gx, gy):
            return
        cur = cell_rotations.get((gx, gy))
        if cur is None:
            val = self.get_tile(gx, gy)
            cur = per_tile_rotations.get(val, 0)
        new = (cur + step) % 360
        if new == 0:
            cell_rotations.pop((gx, gy), None)
        else:
            cell_rotations[(gx, gy)] = new
        self._draw_cell(gx, gy)
        save_turn_data()

    def get_tile(self, gx: int, gy: int) -> int:
        if not self.in_bounds(gx, gy):
            return 0
        return self.grid[gy][gx]

    def world_rect_for_cell(self, gx: int, gy: int) -> pygame.Rect:
        return pygame.Rect(gx * self.tile, gy * self.tile, self.tile, self.tile)

    def get_solid_tile_rects_in_rect(self, rect: pygame.Rect) -> List[pygame.Rect]:
        left = clamp(rect.left // self.tile, 0, max(0, self.cols - 1))
        right = clamp((rect.right - 1) // self.tile, 0, max(0, self.cols - 1))
        top = clamp(rect.top // self.tile, 0, max(0, self.rows - 1))
        bottom = clamp((rect.bottom - 1) // self.tile, 0, max(0, self.rows - 1))

        rects: List[pygame.Rect] = []
        for gy in range(int(top), int(bottom) + 1):
            for gx in range(int(left), int(right) + 1):
                val = self.grid[gy][gx]
                if val != 0 and val not in DECORATION_IDS:
                    rects.append(self.world_rect_for_cell(gx, gy))
        return rects

    def get_all_cells_in_rect(self, rect: pygame.Rect) -> List[Tuple[int, int]]:
        left = int(clamp(rect.left // self.tile, 0, self.cols - 1))
        right = int(clamp((rect.right - 1) // self.tile, 0, self.cols - 1))
        top = int(clamp(rect.top // self.tile, 0, self.rows - 1))
        bottom = int(clamp((rect.bottom - 1) // self.tile, 0, self.rows - 1))
        cells = []
        for gy in range(top, bottom + 1):
            for gx in range(left, right + 1):
                cells.append((gx, gy))
        return cells

    def in_bounds(self, gx: int, gy: int) -> bool:
        return 0 <= gx < self.cols and 0 <= gy < self.rows

    def draw_visible(self, surface: pygame.Surface, camx: int, camy: int, render_w: int, render_h: int):
        if self.cols == 0 or self.rows == 0:
            return

        left = max(0, camx // self.tile)
        right = min(self.cols - 1, (camx + render_w - 1) // self.tile)
        top = max(0, camy // self.tile)
        bottom = min(self.rows - 1, (camy + render_h - 1) // self.tile)

        for gy in range(top, bottom + 1):
            ty = gy * self.tile - camy
            row = self.grid[gy]
            for gx in range(left, right + 1):
                val = row[gx]
                if val == 0 or val in DECORATION_IDS:
                    continue
                img = self.tile_images.get(val)
                pos = (gx * self.tile - camx, ty)
                rot = get_tile_rotation(val, gx, gy) or 0
                if img:
                    self._draw_image_with_rotation(surface, img, pos, rot)
                else:
                    pygame.draw.rect(surface, (200, 200, 200), (pos[0], pos[1], self.tile, self.tile))

        for gy in range(top, bottom + 1):
            ty = gy * self.tile - camy
            row = self.grid[gy]
            for gx in range(left, right + 1):
                val = row[gx]
                if val == 0 or val not in DECORATION_IDS:
                    continue
                if val in COLLECTABLE_TILE_IDS:
                    continue
                img = self.tile_images.get(val)
                pos = (gx * self.tile - camx, ty)
                rot = get_tile_rotation(val, gx, gy) or 0
                if img:
                    self._draw_image_with_rotation(surface, img, pos, rot)
                else:
                    if val == SPAWN_TILE_ID:
                        tmp = pygame.Surface((self.tile, self.tile), pygame.SRCALPHA)
                        tmp.fill((0, 220, 0, 120))
                        self._draw_image_with_rotation(surface, tmp, pos, rot)
                        pygame.draw.rect(surface, (0, 150, 0), (pos[0], pos[1], self.tile, self.tile), 2)
                    else:
                        tmp = pygame.Surface((self.tile, self.tile), pygame.SRCALPHA)
                        tmp.fill((160, 40, 40, 180))
                        self._draw_image_with_rotation(surface, tmp, pos, rot)

def spawn_pos_from_cell(gx: int, gy: int) -> Tuple[int, int]:
    sx = gx * TILE + (TILE - PLAYER_HITBOX_WIDTH) // 2
    sy = gy * TILE + TILE - PLAYER_HITBOX_HEIGHT
    return sx, sy

def generate_group_id(cells: List[List[int]]) -> str:
    key = "|".join(f"{int(c[0])},{int(c[1])}" for c in sorted(cells))
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]

def normalize_loaded_doors(raw_doors: Any, grid_obj: Grid) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not raw_doors:
        return out

    if isinstance(raw_doors, dict):
        groups = raw_doors.get("groups") or raw_doors.get("doors") or raw_doors.get("groups_list")
        if isinstance(groups, list):
            for g in groups:
                try:
                    if isinstance(g, dict) and "cells" in g:
                        cells = [[int(c[0]), int(c[1])] for c in g.get("cells", [])]
                        orig = g.get("original_tiles", [])
                        if not orig:
                            orig = [int(grid_obj.get_tile(c[0], c[1])) for c in cells]
                        opened = bool(g.get("opened", False) or any(grid_obj.get_tile(c[0], c[1]) in DOOR_OPEN_MAP.values() for c in cells))
                        gid = str(g.get("id") or generate_group_id(cells))
                        out.append({"id": gid, "cells": cells, "original_tiles": [int(t) for t in orig], "opened": opened})
                except Exception:
                    continue
            return out

    if isinstance(raw_doors, list) and raw_doors and all(isinstance(d, (list, tuple)) and len(d) == 2 for d in raw_doors):
        for pair in raw_doors:
            try:
                gx = int(pair[0]); gy = int(pair[1])
                cells = [[gx, gy]]
                orig = [int(grid_obj.get_tile(gx, gy))]
                gid = generate_group_id(cells)
                opened = grid_obj.get_tile(gx, gy) in DOOR_OPEN_MAP.values()
                out.append({"id": gid, "cells": cells, "original_tiles": orig, "opened": opened})
            except Exception:
                continue
        return out

    if isinstance(raw_doors, list):
        for group in raw_doors:
            try:
                if isinstance(group, (list, tuple)):
                    cells = []
                    origs = []
                    for c in group:
                        if isinstance(c, (list, tuple)) and len(c) == 2:
                            gx = int(c[0]); gy = int(c[1])
                            cells.append([gx, gy])
                            origs.append(int(grid_obj.get_tile(gx, gy)))
                    if cells:
                        gid = generate_group_id(cells)
                        opened = any(grid_obj.get_tile(c[0], c[1]) in DOOR_OPEN_MAP.values() for c in cells)
                        out.append({"id": gid, "cells": cells, "original_tiles": origs, "opened": opened})
            except Exception:
                continue
    return out

def load_doors_file(grid_obj: Grid) -> List[Dict[str, Any]]:
    raw = None
    if os.path.exists(DOORS_FILE):
        raw = load_json_or_default(DOORS_FILE, None)
    if raw is None and os.path.exists(DATA_FILE):
        m = load_json_or_default(DATA_FILE, {})
        raw = m.get("doors", None)
    return normalize_loaded_doors(raw, grid_obj)

def save_doors_file():
    try:
        groups = []
        for g in DOORS_META:
            groups.append({
                "id": g.get("id"),
                "cells": [[int(c[0]), int(c[1])] for c in g.get("cells", [])],
                "original_tiles": [int(t) for t in g.get("original_tiles", [])],
                "opened": bool(g.get("opened", False))
            })
        payload = {"version": 1, "groups": groups}
        safe_write_json(DOORS_FILE, payload)
    except Exception as e:
        pass

def save_keys_file():
    try:
        payload = {"version": 1, "keys": []}
        for k in KEYS_META:
            payload["keys"].append({
                "id": k.get("id"),
                "cell": [int(c) for c in k.get("cell", [])]
            })
        safe_write_json(KEYS_PATH, payload)
    except Exception as e:
        pass

def save_map(filename: str, grid_obj: Grid, keys_meta=None, doors_meta=None):
    try:
        out = {"grid": grid_obj.grid}
        if keys_meta is not None:
            out["keys"] = keys_meta
        if doors_meta is not None:
            out["doors"] = [[[int(c[0]), int(c[1])] for c in group.get("cells", [])] if isinstance(group, dict) else [[int(c[0]), int(c[1])] for c in group] for group in doors_meta]
        safe_write_json(filename, out)
        try:
            if doors_meta is not None:
                save_doors_file()
        except Exception:
            pass
        try:
            if keys_meta is not None:
                save_keys_file()
        except Exception:
            pass
    except Exception as e:
        pass

TILE_IMAGES = load_tile_images(TILE)

_coin_path = os.path.join("assets", "coin.png")
try:
    coinimg = pygame.image.load(_coin_path).convert_alpha()
    coinimg = pygame.transform.scale(coinimg, (TILE, TILE))
except Exception:
    coinimg = None

_key_path = os.path.join("assets", "key.png")
try:
    keyimg = pygame.image.load(_key_path).convert_alpha()
    keyimg = pygame.transform.scale(keyimg, (TILE, TILE))
except Exception:
    keyimg = None

_mini_path = os.path.join("assets", "mini.png")
try:
    miniimg = pygame.image.load(_mini_path).convert_alpha()
    miniimg = pygame.transform.scale(miniimg, (TILE, TILE))
except Exception:
    tmp = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    tmp.fill((200, 0, 200))
    miniimg = tmp

DEFAULT_MAP_DATA = [
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 83, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 83, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 83, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 86, 86, 86, 0, 0, 88, 88, 88, 0, 0, 0, 0, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
]

map_json = load_json_or_default(DATA_FILE, {"grid": DEFAULT_MAP_DATA, "keys": [], "doors": []})
grid_data = map_json.get("grid", DEFAULT_MAP_DATA)
if not grid_data or not isinstance(grid_data[0], list):
    grid_data = DEFAULT_MAP_DATA

grid = Grid(TILE, grid_data, TILE_IMAGES)

RUNTIME_COLLECTED_KEYS: set = set()
RUNTIME_COLLECTED_KEYS.clear()
def collect_key_at_cell(gx: int, gy: int) -> bool:
    for i, meta in enumerate(KEYS_META):
        cell = meta.get("cell", [])
        if len(cell) == 2 and int(cell[0]) == gx and int(cell[1]) == gy:
            key_id = meta.get("id")
            if not key_id:
                return False

            if key_id in RUNTIME_COLLECTED_KEYS:
                return False

            opened_any = False
            door_indices = find_door_indices_by_id(key_id)
            for d_idx in door_indices:
                if 0 <= d_idx < len(doors):
                    doors[d_idx].open()
                    opened_any = True

            RUNTIME_COLLECTED_KEYS.add(key_id)
            KEYS_META.pop(i)
            grid.set_tile(gx, gy, 0)
            cx, cy = gx * TILE + TILE // 2, gy * TILE + TILE // 2
            emit_particles(cx, cy, 40, speed_spread=80, life_spread=1.2, color=(200, 200, 80), radius_range=(2, 5))
            key_s.play()
            return opened_any

    return False

def dedupe_doors_meta():
    global DOORS_META
    seen = {}
    new = []
    for g in DOORS_META:
        gid = str(g.get("id") or "")
        if not gid:
            gid = generate_group_id(g.get("cells", []))
        if gid in seen:
            continue
        seen[gid] = True
        new.append({
            "id": gid,
            "cells": [[int(c[0]), int(c[1])] for c in g.get("cells", [])],
            "original_tiles": [int(t) for t in g.get("original_tiles", [])] if g.get("original_tiles") else [int(grid.get_tile(c[0], c[1])) for c in g.get("cells", [])],
            "opened": bool(g.get("opened", False))
        })
    DOORS_META = new
    try:
        save_doors_file()
    except Exception:
        pass

DOORS_META = load_doors_file(grid)
dedupe_doors_meta()

def find_door_groups_from_grid(grid_obj: Grid) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []
    visited = set()
    for gy in range(grid_obj.rows):
        for gx in range(grid_obj.cols):
            if (gx, gy) in visited:
                continue
            tid = grid_obj.get_tile(gx, gy)
            if tid in DOOR_TILE_IDS or tid in DOOR_OPEN_MAP.values():
                stack = [(gx, gy)]
                group = []
                while stack:
                    cx, cy = stack.pop()
                    if (cx, cy) in visited:
                        continue
                    ct = grid_obj.get_tile(cx, cy)
                    if not (ct in DOOR_TILE_IDS or ct in DOOR_OPEN_MAP.values()):
                        continue
                    visited.add((cx, cy))
                    group.append([int(cx), int(cy)])
                    for nx, ny in ((cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)):
                        if 0 <= nx < grid_obj.cols and 0 <= ny < grid_obj.rows and (nx, ny) not in visited:
                            nt = grid_obj.get_tile(nx, ny)
                            if nt in DOOR_TILE_IDS or nt in DOOR_OPEN_MAP.values():
                                stack.append((nx, ny))
                if group:
                    original_tiles = [int(grid_obj.get_tile(c[0], c[1])) for c in group]
                    gid = generate_group_id(group)
                    opened = any(t in DOOR_OPEN_MAP.values() for t in original_tiles)
                    found.append({"id": gid, "cells": group, "original_tiles": original_tiles, "opened": opened})
    return found

def groups_equal(g1: Any, g2: Any) -> bool:
    try:
        a = g1.get("cells") if isinstance(g1, dict) else g1
        b = g2.get("cells") if isinstance(g2, dict) else g2
        s1 = set(tuple(c) for c in a)
        s2 = set(tuple(c) for c in b)
        return s1 == s2
    except Exception:
        return False

KEYS_META = []
if os.path.exists(KEYS_PATH):
    raw_keys_file = load_json_or_default(KEYS_PATH, {})
    raw_keys = raw_keys_file.get("keys", []) if isinstance(raw_keys_file, dict) else raw_keys_file
else:
    raw_keys = map_json.get("keys", []) or []

for i, k in enumerate(raw_keys):
    try:
        if isinstance(k, list) and len(k) == 2:
            gx, gy = int(k[0]), int(k[1])
            kid = f"key_{gx}_{gy}"
            KEYS_META.append({"id": kid, "cell": [gx, gy]})
        elif isinstance(k, dict):
            cell = k.get("cell")
            kid = k.get("id") or f"key_{i}"
            KEYS_META.append({"id": kid, "cell": [int(cell[0]), int(cell[1])] if cell else []})
    except Exception:
        continue

default_spawn_cell = (2, 2)
spawn_point: Tuple[int, int] = spawn_pos_from_cell(*default_spawn_cell)

spawn_positions: List[Tuple[int, int]] = []
for gy in range(grid.rows):
    for gx in range(grid.cols):
        if grid.get_tile(gx, gy) == SPAWN_TILE_ID:
            spawn_positions.append((gx, gy))

if spawn_positions:
    gx_sel, gy_sel = max(spawn_positions, key=lambda p: (p[1], -p[0]))
    spawn_point = spawn_pos_from_cell(gx_sel, gy_sel)
else:
    gx, gy = default_spawn_cell
    if grid.in_bounds(gx, gy):
        grid.set_tile(gx, gy, SPAWN_TILE_ID, record=False)
        spawn_point = spawn_pos_from_cell(gx, gy)

def _on_collect_cb(c: Collectable):
    global score
    score += c.value
    emit_particles(c.rect.centerx, c.rect.centery, 20, speed_spread=80, life_spread=1.0, color=(255, 220, 60), radius_range=(2, 4))

def add_collectable_at_cell(gx: int, gy: int):
    remove_collectable_at_cell(gx, gy)
    if not grid.in_bounds(gx, gy):
        return
    img = coinimg
    if img is None:
        tmp = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        pygame.draw.circle(tmp, (255, 220, 40), (TILE // 2, TILE // 2), max(6, TILE // 3))
        img = tmp
    c = Collectable.from_tile_center(gx, gy, TILE, img, on_collect=_on_collect_cb, value=1, respawn_time=None, sound=coin_s)
    coins.append(c)

def remove_collectable_at_cell(gx: int, gy: int):
    to_remove = []
    for c in coins:
        cx = (int(c.x0) + c.w // 2) // TILE
        cy = (int(c.y0) + c.h // 2) // TILE
        if (cx, cy) == (gx, gy):
            to_remove.append(c)
    for c in to_remove:
        try:
            coins.remove(c)
        except ValueError:
            pass

for gy in range(grid.rows):
    for gx in range(grid.cols):
        if grid.get_tile(gx, gy) in COLLECTABLE_TILE_IDS:
            add_collectable_at_cell(gx, gy)

def sync_key_door_objects():
    global doors, door_id_map
    doors.clear()
    door_id_map.clear()
    for idx, entry in enumerate(DOORS_META):
        try:
            door_id = str(entry.get("id") or generate_group_id(entry.get("cells", [])))
            cells = [tuple(map(int, c)) for c in entry.get("cells", [])]
            orig_tiles = [int(t) for t in entry.get("original_tiles", [])] if entry.get("original_tiles") else [grid.get_tile(c[0], c[1]) for c in cells]
            dr = Door(cells, grid, door_id, original_tiles=orig_tiles)
            try:
                for (gx, gy), orig in zip(dr.cells, orig_tiles):
                    grid.set_tile(gx, gy, int(orig), record=False)
                    grid._draw_cell(gx, gy)
            except Exception:
                pass
            runtime_open = any(grid.get_tile(c[0], c[1]) in DOOR_OPEN_MAP.values() for c in dr.cells)
            dr.opened = bool(runtime_open)
            doors.append(dr)
            door_id_map[dr.id] = idx
        except Exception:
            doors.append(Door([], grid, f"__broken_{idx}", original_tiles=[]))
            door_id_map[f"__broken_{idx}"] = idx

sync_key_door_objects()

def add_door_group(cells: List[Tuple[int, int]], gid: Optional[str] = None):
    if not cells:
        return
    cells_list = [[int(c[0]), int(c[1])] for c in cells]
    original_tiles = [int(grid.get_tile(c[0], c[1])) for c in cells_list]
    if gid:
        group_id = str(gid).strip()
        if group_id == "":
            group_id = generate_group_id(cells_list)
    else:
        group_id = generate_group_id(cells_list)
    DOORS_META.append({"id": group_id, "cells": cells_list, "original_tiles": original_tiles, "opened": False})
    sync_key_door_objects()
    try:
        save_doors_file()
    except Exception as e:
        pass

def remove_door_group_by_index(idx: int):
    if not (0 <= idx < len(DOORS_META)):
        return
    removed = DOORS_META.pop(idx)
    sync_key_door_objects()
    try:
        save_doors_file()
    except Exception as e:
        pass

def add_key_for_pair(key_cell: Tuple[int, int], key_id: Optional[str] = None):
    gx, gy = key_cell
    if not grid.in_bounds(gx, gy):
        return

    for i, meta in enumerate(KEYS_META):
        cell = meta.get("cell", [])
        if len(cell) == 2 and cell[0] == gx and cell[1] == gy:
            KEYS_META.pop(i)
            break

    if key_id is None or str(key_id).strip() == "":
        key_id = f"key_{gx}_{gy}_{random.randint(1000,9999)}"
    entry = {"id": str(key_id), "cell": [gx, gy]}
    KEYS_META.append(entry)
    grid.set_tile(gx, gy, KEY_TILE_ID)
    try:
        save_keys_file()
    except Exception:
        pass
    sync_key_door_objects()

def remove_key_meta_by_index(idx: int):
    global KEYS_META
    if not (0 <= idx < len(KEYS_META)):
        return
    try:
        del KEYS_META[idx]
    except Exception:
        return
    sync_key_door_objects()
    try:
        save_keys_file()
    except Exception:
        pass

def remove_key_meta_by_cell(gx: int, gy: int):
    for i in reversed(range(len(KEYS_META))):
        meta = KEYS_META[i]
        cell = meta.get("cell", [])
        if len(cell) == 2 and cell[0] == gx and cell[1] == gy:
            KEYS_META.pop(i)
    if grid.in_bounds(gx, gy) and grid.get_tile(gx, gy) == KEY_TILE_ID:
        grid.set_tile(gx, gy, 0)
    sync_key_door_objects()
    try:
        save_keys_file()
    except Exception:
        pass

def find_door_indices_by_id(door_id: str) -> List[int]:
    out = []
    for idx, g in enumerate(DOORS_META):
        if str(g.get("id")) == str(door_id):
            out.append(idx)
    return out

sync_key_door_objects()

found_key_cells: List[Tuple[int, int]] = []
for gy in range(grid.rows):
    for gx in range(grid.cols):
        if grid.get_tile(gx, gy) == KEY_TILE_ID:
            found_key_cells.append((gx, gy))

for (gx, gy) in found_key_cells:
    exists = False
    for meta in KEYS_META:
        cell = meta.get("cell", [])
        if len(cell) >= 2 and int(cell[0]) == gx and int(cell[1]) == gy:
            exists = True
            break
    if not exists:
        kid = f"key_{gx}_{gy}"
        KEYS_META.append({"id": kid, "cell": [gx, gy]})
try:
    save_keys_file()
except Exception:
    pass

RUNTIME_COLLECTED_KEY_IDS: set = set()

def collect_key_at_cell(gx: int, gy: int) -> bool:
    for meta in KEYS_META:
        cell = meta.get("cell", [])
        if len(cell) == 2 and int(cell[0]) == gx and int(cell[1]) == gy:
            key_id = meta.get("id")
            if not key_id:
                return False

            if key_id in RUNTIME_COLLECTED_KEYS:
                return False

            opened_any = False
            door_indices = find_door_indices_by_id(key_id)
            for d_idx in door_indices:
                if 0 <= d_idx < len(doors):
                    doors[d_idx].open()
                    opened_any = True

            RUNTIME_COLLECTED_KEYS.add(key_id)
            grid.set_tile(gx, gy, 0)
            cx, cy = gx * TILE + TILE // 2, gy * TILE + TILE // 2
            emit_particles(cx, cy, 40, speed_spread=80, life_spread=1.2, color=(200, 200, 80), radius_range=(2, 5))
            key_s.play()
            return opened_any

    return False

keys_file = load_json_or_default(KEYS_PATH, {})
for k in keys_file.get("keys", []):
    grid.set_tile(k["cell"][0], k["cell"][1], 67)

class Player:
    def __init__(self, x: float, y: float, frames: List[pygame.Surface]):
        self.frames = frames
        self.original_frames = frames
        self.image = frames[0]
        self.w = PLAYER_HITBOX_WIDTH
        self.h = PLAYER_HITBOX_HEIGHT
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.rect = pygame.Rect(int(self.x), int(self.y), self.w, self.h)
        self.last_dash = 0.0

        self.frame_timer = 0.0
        self.frame_i = 0
        self.grounded = False
        self.flip = False
        self.state = "idle"

        self.foot_timer = 0.0

        self.wall_touch_dir = 0
        self.wall_jump_used = False
        self.wall_jump_horz = H_SPEED * 0.8

        self.request_wall_jump = False

        self.coyote_time_max = 0.10
        self.coyote_timer = 0.0

        self.jump_buffer_max = 0.12
        self.jump_buffer_timer = 0.0

        self.climbing = False
        self.climb_speed = 300.0
        self.climb_request_y = 0.0

        self._last_checkpoint_cell: Optional[Tuple[int, int]] = None

        self.mini_mode: bool = False
        self._saved_w = self.w
        self._saved_h = self.h
        self._saved_frames: Optional[List[pygame.Surface]] = None
        self._saved_image: Optional[pygame.Surface] = None

    @property
    def center(self):
        return (self.rect.centerx, self.rect.centery)

    def dash(self):
        if self.mini_mode:
            return
        if self.last_dash <= 0.0:
            direction = -1 if self.flip else 1
            self.vx = direction * H_SPEED
            self.last_dash = DASH_COOLDOWN
            self.vy -= 80
            emit_particles(self.rect.centerx, self.rect.bottom - 4, DASH_PARTICLES, speed_spread=80, life_spread=1.0, color=(255, 220, 120), radius_range=(2, 4))
            dash_s.play()

    def toggle_mini_mode(self, mini_img: Optional[pygame.Surface] = None):
        if not self.mini_mode:
            self.mini_mode = True
            self._saved_w = self.w
            self._saved_h = self.h
            self._saved_frames = list(self.original_frames)
            self._saved_image = self.image
            self.w = TILE
            self.h = TILE
            if mini_img:
                mimg = mini_img
            else:
                mimg = pygame.transform.scale(self.original_frames[0], (TILE, TILE))
            self.original_frames = [mimg]
            self.image = self.original_frames[0]
            bottom = self.rect.bottom
            centerx = self.rect.centerx
            self.x = centerx - self.w / 2
            self.y = bottom - self.h
            self.rect = pygame.Rect(int(self.x), int(self.y), self.w, self.h)
            self.wall_jump_used = True
        else:
            bottom = self.rect.bottom
            centerx = self.rect.centerx
            target_rect = pygame.Rect(int(centerx - self._saved_w / 2), int(bottom - self._saved_h), int(self._saved_w), int(self._saved_h))
            blocking = False
            try:
                solid_rects = grid.get_solid_tile_rects_in_rect(target_rect)
                for t in solid_rects:
                    if target_rect.colliderect(t):
                        blocking = True
                        break
            except Exception:
                blocking = True

            if blocking:
                try:
                    dash_s.play()
                except Exception:
                    pass
                return

            self.mini_mode = False
            self.w = self._saved_w
            self.h = self._saved_h
            if self._saved_frames is not None:
                self.original_frames = list(self._saved_frames)
                self.image = self.original_frames[0]
            elif self._saved_image is not None:
                self.image = self._saved_image
            bottom = self.rect.bottom
            centerx = self.rect.centerx
            self.x = centerx - self.w / 2
            self.y = bottom - self.h
            self.rect = pygame.Rect(int(self.x), int(self.y), self.w, self.h)
            self.wall_jump_used = False

    def apply_input(self, pressed, w_pressed_now: bool):
        if debug:
            speed = H_SPEED * 2
            self.vx = 0.0
            self.vy = 0.0
            if pressed[pygame.K_a] or pressed[pygame.K_LEFT]:
                self.vx = -speed
                self.flip = True
            if pressed[pygame.K_d] or pressed[pygame.K_RIGHT]:
                self.vx = speed
                self.flip = False
            if pressed[pygame.K_w] or pressed[pygame.K_SPACE] or pressed[pygame.K_UP]:
                self.vy = -speed
            self.request_wall_jump = False
            self.jump_buffer_timer = 0.0
            return

        self.climb_request_y = 0.0
        if pressed[pygame.K_w] or pressed[pygame.K_UP]:
            self.climb_request_y = -1.0
        elif pressed[pygame.K_s] or pressed[pygame.K_DOWN]:
            self.climb_request_y = 1.0

        if self.climbing:
            if (pressed[pygame.K_a] or pressed[pygame.K_LEFT] or pressed[pygame.K_d] or pressed[pygame.K_RIGHT] or w_pressed_now):
                self.climbing = False
                if w_pressed_now:
                    self.vy = JUMP_V
                    if pressed[pygame.K_a] or pressed[pygame.K_LEFT]:
                        self.vx = -H_SPEED * 0.8
                    elif pressed[pygame.K_d] or pressed[pygame.K_RIGHT]:
                        self.vx = H_SPEED * 0.8
                    else:
                        self.vx = 0.0
                    return
                self.vy = self.vy * 0.5

        if pressed[pygame.K_a] or pressed[pygame.K_LEFT]:
            self.vx -= 20.0
            self.flip = True
        if pressed[pygame.K_d] or pressed[pygame.K_RIGHT]:
            self.vx += 20.0
            self.flip = False

        if w_pressed_now and not self.climbing:
            self.jump_buffer_timer = self.jump_buffer_max

        self.request_wall_jump = False
        if (w_pressed_now and not self.grounded and self.wall_touch_dir != 0 and not self.wall_jump_used and not self.climbing and not self.mini_mode):
            self.request_wall_jump = True

        self.vx = clamp(self.vx, -H_SPEED, H_SPEED)

    def try_move(self, dt: float, grid: Grid) -> Optional[str]:
        global spawn_point, shake_time, shake_mag
        if debug:
            self.x += self.vx * dt
            self.y += self.vy * dt
            self.rect.topleft = (int(self.x), int(self.y))
            return None

        dx = self.vx * dt
        dy = self.vy * dt
        new_x = self.x + dx
        new_y = self.y

        test_rect = pygame.Rect(int(new_x), int(self.y), self.w, self.h)
        tile_rects = grid.get_solid_tile_rects_in_rect(test_rect)
        self.wall_touch_dir = 0
        for t in tile_rects:
            if test_rect.colliderect(t):
                tx = t.left // grid.tile
                ty = t.top // grid.tile
                tid = grid.get_tile(tx, ty)

                if tid == 70 and self.last_dash > 1.5:
                    grid.set_tile(tx, ty, 0)
                    emit_particles(
                        tx * grid.tile + grid.tile // 2,
                        ty * grid.tile + grid.tile // 2,
                        40,
                        speed_spread=120,
                        life_spread=1.5,
                        color=(255, 250, 90),
                        radius_range=(3, 7)
                    )
                    shake_time = 0.33
                    shake_mag = 7.0
                    continue

                if test_rect.colliderect(t):
                    if dx > 0:
                        new_x = t.left - self.w
                        self.wall_touch_dir = 1
                    elif dx < 0:
                        new_x = t.right
                        self.wall_touch_dir = -1
                    self.vx = 0
                    break

        new_y += dy
        test_rect = pygame.Rect(int(new_x), int(new_y), self.w, self.h)
        tile_rects = grid.get_solid_tile_rects_in_rect(test_rect)
        self.grounded = False
        for t in tile_rects:
            if test_rect.colliderect(t):
                tx = t.left // grid.tile
                ty = t.top // grid.tile
                tid = grid.get_tile(tx, ty)

                if tid == 70 and self.last_dash > 1.5:
                    grid.set_tile(tx, ty, 0)
                    emit_particles(
                        tx * grid.tile + grid.tile // 2,
                        ty * grid.tile + grid.tile // 2,
                        40,
                        speed_spread=120,
                        life_spread=1.5,
                        color=(255, 250, 90),
                        radius_range=(3, 7)
                    )
                    shake_time = 0.33
                    shake_mag = 7.0
                    continue

                if test_rect.colliderect(t):
                    if dy > 0:
                        new_y = t.top - self.h
                        self.vy = 0.0
                        self.grounded = True
                        self.wall_jump_used = False
                        self.coyote_timer = self.coyote_time_max
                        self.request_wall_jump = False
                        self.wall_touch_dir = 0
                        self.climbing = False
                    elif dy < 0:
                        new_y = t.bottom
                        self.vy = 0
                    break

        self.x = new_x
        self.y = new_y
        self.rect.topleft = (int(self.x), int(self.y))

        if not self.grounded and self.wall_touch_dir == 0 and not self.climbing:
            left_rect = self.rect.move(-1, 0)
            right_rect = self.rect.move(1, 0)
            left_tiles = grid.get_solid_tile_rects_in_rect(left_rect)
            right_tiles = grid.get_solid_tile_rects_in_rect(right_rect)
            for t in left_tiles:
                if left_rect.colliderect(t):
                    self.wall_touch_dir = -1
                    break
            for t in right_tiles:
                if right_rect.colliderect(t):
                    self.wall_touch_dir = 1
                    break

        cells = grid.get_all_cells_in_rect(self.rect)
        on_chain = False
        for (gx, gy) in cells:
            tid = grid.get_tile(gx, gy)

            if tid == 70 and self.last_dash > 1.5:
                grid.set_tile(gx, gy, 0)
                emit_particles(
                    gx * grid.tile + grid.tile // 2,
                    gy * grid.tile + grid.tile // 2,
                    40,
                    speed_spread=120,
                    life_spread=1.5,
                    color=(255, 250, 90),
                    radius_range=(3, 7)
                )
                shake_time = 0.33
                shake_mag = 7.0

            if tid == SPAWN_TILE_ID:
                new_spawn = spawn_pos_from_cell(gx, gy)
                if spawn_point != new_spawn:
                    spawn_point = new_spawn
                    self._last_checkpoint_cell = (gx, gy)

            if tid in TILES_WITH_CUSTOM_HITBOX:
                custom_hitbox = get_tile_hitbox_rect(tid, gx, gy, grid.tile)
                if custom_hitbox and self.rect.colliderect(custom_hitbox):
                    if tid in (86, 88):
                        die_s.play()
                        return "death"
                    elif tid == 83:
                        on_chain = True
            elif self.y <= 0 or self.y >= grid.rows * grid.tile:
                die_s.play()
                return "death"
            elif tid in DEADLY_TILES:
                die_s.play()
                return "death"
            if tid == 9:
                self.vyh += -550

            if tid == KEY_TILE_ID:
                collected = collect_key_at_cell(gx, gy)
                if collected:
                    pass

        if not self.climbing and on_chain and self.climb_request_y != 0.0:
            self.climbing = True
            self.vy = 0.0
            self.vx = 0.0
            self.grounded = False
            self.coyote_timer = 0.0
            self.jump_buffer_timer = 0.0

        if self.climbing and not on_chain:
            self.climbing = False

        return None

    def update_animation(self, dt: float):
        if self.climbing:
            self.state = "climb"
        else:
            self.state = "idle" if abs(self.vx) < 64 else "run"

        speed = 2.0 if self.state == "idle" else 1.0
        if self.state in ("idle", "run"):
            self.frame_timer += dt * speed
            total = max(1, len(self.original_frames))
            self.frame_i = int(self.frame_timer) % total
            self.image = self.original_frames[self.frame_i]
            if self.frame_timer > 1000:
                self.frame_timer = self.frame_timer % total
        elif self.state == "climb":
            self.frame_timer += dt * (1.5 if abs(self.vy) > 0.1 else 0.5)
            total = max(1, len(self.original_frames))
            self.frame_i = int(self.frame_timer) % total
            self.image = self.original_frames[self.frame_i]
            if self.frame_timer > 1000:
                self.frame_timer = self.frame_timer % total
        else:
            self.image = self.original_frames[0]

    def update(self, dt: float, grid: Grid) -> Optional[str]:
        if self.coyote_timer > 0:
            self.coyote_timer -= dt
        if self.jump_buffer_timer > 0:
            self.jump_buffer_timer -= dt

        if self.climbing:
            self.vy = self.climb_request_y * self.climb_speed
            self.vx = 0.0
            self.grounded = False
            self.coyote_timer = 0.0
            self.jump_buffer_timer = 0.0
        else:
            self.vy += GRAVITY * dt

        death = self.try_move(dt, grid)

        if self.request_wall_jump and not self.climbing:
            if not self.mini_mode and self.wall_touch_dir != 0 and not self.wall_jump_used:
                self.vy = JUMP_V
                self.vx = -self.wall_touch_dir * self.wall_jump_horz
                self.wall_jump_used = True
                self.flip = (self.vx < 0)
            self.request_wall_jump = False

        if self.jump_buffer_timer > 0 and (self.grounded or self.coyote_timer > 0):
            self.vy = JUMP_V
            self.jump_buffer_timer = 0.0
            self.coyote_timer = 0.0

        self.update_animation(dt)
        if not debug:
            if not self.climbing:
                self.vx *= 0.95
                if abs(self.vx) < 0.01:
                    self.vx = 0.0
            else:
                self.vx = 0.0
            self.last_dash = max(self.last_dash - dt, 0.0)

            if self.grounded and self.state == "run":
                self.foot_timer += dt
                interval = 0.06
                while self.foot_timer >= interval:
                    self.foot_timer -= interval
                    emit_particles(self.rect.centerx, self.rect.bottom - 4, WALK_PARTICLES, speed_spread=40, life_spread=0.6, color=(180, 180, 180), radius_range=(1, 3))
            else:
                self.foot_timer = min(self.foot_timer, 0.02)
        return death

    def draw(self, surf: pygame.Surface, camx: int, camy: int):
        img = self.image
        if not self.mini_mode:
            if self.state == "run" and not self.mini_mode:
                img = pygame.transform.rotate(img, -10)
            if self.flip and not self.mini_mode:
                img = pygame.transform.flip(img, True, False)
            img_x = self.rect.centerx - img.get_width() // 2 - camx
            img_y = self.rect.centery - img.get_height() // 2 - camy
            surf.blit(img, (img_x, img_y))
            return img_x, img_y, img.get_width(), img.get_height()
        else:
            if self.flip:
                img = pygame.transform.flip(img, True, False)
            img_x = self.rect.centerx - img.get_width() // 2 - camx
            img_y = self.rect.centery - img.get_height() // 2 - camy
            surf.blit(img, (img_x, img_y))
            return img_x, img_y, img.get_width(), img.get_height()

player_frames = load_player_frames(PLAYER_SIZE)
player = Player(spawn_point[0], spawn_point[1], player_frames)

camx, camy = 0.0, 0.0
shake_x, shake_y = 0, 0
shake_time = 0.0
shake_mag = 0.0

palette_ids = sorted(list(TILE_IMAGES.keys())) if TILE_IMAGES else [0]

def screen_to_world(mx: int, my: int, camx_local: float, camy_local: float) -> Tuple[int, int]:
    wx = int(mx / ZOOM) + int(camx_local)
    wy = int(my / ZOOM) + int(camy_local)
    return wx, wy

def set_spawn_point_at_grid(gx: int, gy: int, grid_obj: Grid, player_obj: Player):
    global spawn_point
    if not grid_obj.in_bounds(gx, gy):
        return None
    for y in range(grid_obj.rows):
        for x in range(grid_obj.cols):
            if grid_obj.get_tile(x, y) == SPAWN_TILE_ID and not (x == gx and y == gy):
                grid_obj.set_tile(x, y, 0, record=False)
    grid_obj.set_tile(gx, gy, SPAWN_TILE_ID)
    spawn_point = spawn_pos_from_cell(gx, gy)
    player_obj.x, player_obj.y = spawn_point
    player_obj.rect.topleft = (int(player_obj.x), int(player_obj.y))
    return SPAWN_TILE_ID

try:
    BG = pygame.image.load(os.path.join("assets", BG_PATH)).convert_alpha()
    BG = pygame.transform.scale(BG, (W, H))
except Exception:
    BG = pygame.Surface((W, H))
    BG.fill((40, 40, 40))
NEWBG = change_brightness(BG, -100)

factory = pygame.image.load("assets/p1.png").convert_alpha()
factory = pygame.transform.scale(factory, (W/2, H/2))
factory = change_brightness(factory, -30)
factoryback = pygame.image.load("assets/p2.png").convert_alpha()
factoryback = pygame.transform.scale(factoryback, (W, H))
factoryrback = pygame.image.load("assets/p3.png").convert_alpha()
factoryrback = pygame.transform.scale(factoryrback, (W, H))
factoryrback = change_brightness(factoryrback, -30)

sync_key_door_objects()

settings = load_json_or_default("settings.json", {})
performance = bool(settings.get("performance", True))

running = True
async def main():
    global running, camx, camy, editor, shake_time, particles, debug, selected_tile, shake_mag
    import platform
    if platform.system() == "Emscripten":
        import js
        js.window.eval("window.is_background_active = true;")
    while running:
        SCREEN.blit(NEWBG, (0, 0))
        if performance:
            SCREEN.blit(factoryback, (0-(camx/3)%W, 0-(camy/5)+H*1.5))
            SCREEN.blit(factoryback, (W-(camx/3)%W, 0-(camy/5)+H*1.5))
            SCREEN.blit(factoryrback, (0-(camx/2)%(W+100), 0-(camy/5)+H*1.5))
            SCREEN.blit(factoryrback, (W+100-(camx/2)%(W+100), 0-(camy/5)+H*1.5))
            SCREEN.blit(factory, (0-(camx/1.5)%W, 0-(camy/5)+H*2))
            SCREEN.blit(factory, (W/2-(camx/1.5)%W, 0-(camy/5)+H*2))
            SCREEN.blit(factory, (W-(camx/1.5)%W, 0-(camy/5)+H*2))
            SCREEN.blit(factory, (W*1.5-(camx/1.5)%W, 0-(camy/5)+H*2))
        dt = clock.tick(FPS_TARGET) / 1000.0
        fps = clock.get_fps()
        render_w = max(1, int(W / ZOOM))
        render_h = max(1, int(H / ZOOM))
        render_surf = pygame.Surface((render_w, render_h), pygame.SRCALPHA)

        w_pressed_now = False
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
                break

            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                    break
                elif ev.key == pygame.K_u:
                    debug = not debug
                elif ev.key == pygame.K_e:
                    editor = not editor
                elif ev.key == pygame.K_F2:
                    save_map(DATA_FILE, grid, keys_meta=KEYS_META, doors_meta=DOORS_META)
                elif ev.key in (pygame.K_q, pygame.K_LSHIFT):
                    player.dash()
                elif pygame.K_0 <= ev.key <= pygame.K_9:
                    selected_tile = ev.key - pygame.K_0
                elif ev.key == pygame.K_LEFTBRACKET:
                    selected_tile = max(0, selected_tile - 1)
                elif ev.key == pygame.K_RIGHTBRACKET:
                    if TILE_IMAGES:
                        max_id = max(TILE_IMAGES.keys())
                        selected_tile = min(max_id, selected_tile + 1)
                elif ev.key == pygame.K_h and editor:
                    selected_tile = SPAWN_TILE_ID
                elif ev.key == pygame.K_p:
                    mx, my = pygame.mouse.get_pos()
                    gx_world, gy_world = screen_to_world(mx, my, camx, camy)
                    selected_tile = grid.get_tile(gx_world // TILE, gy_world // TILE)
                elif ev.key == pygame.K_z and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    if last_changes:
                        gx, gy, old, new = last_changes.pop()
                        grid.set_tile(gx, gy, old, record=False)
                        redo_stack.append((gx, gy, old, new))
                elif ev.key == pygame.K_y and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    if redo_stack:
                        gx, gy, old, new = redo_stack.pop()
                        grid.set_tile(gx, gy, new, record=False)
                        last_changes.append((gx, gy, old, new))
                elif ev.key == pygame.K_t:
                    save_turn_data()
                elif ev.key == pygame.K_r and editor:
                    mx, my = pygame.mouse.get_pos()
                    gx_world, gy_world = screen_to_world(mx, my, camx, camy)
                    gx = gx_world // TILE
                    gy = gy_world // TILE
                    if grid.in_bounds(gx, gy):
                        grid.toggle_cell_rotation(gx, gy, 90)
                elif ev.key == pygame.K_f:
                    player.toggle_mini_mode(miniimg)
                if ev.key in (pygame.K_w, pygame.K_SPACE, pygame.K_UP):
                    w_pressed_now = True

            if ev.type == pygame.MOUSEBUTTONDOWN:
                mx, my = pygame.mouse.get_pos()
                palette_tile_px = int(TILE * ZOOM)
                num_tiles = len(palette_ids)
                pal_cols = PALETTE_COLS
                pal_rows = (num_tiles + pal_cols - 1) // pal_cols
                cell_w = palette_tile_px + 4
                palette_w = pal_cols * cell_w + PALETTE_PADDING * 2
                palette_h = pal_rows * cell_w + PALETTE_PADDING * 2
                pal_x = W - palette_w - 8
                pal_y = 8

                if not editor and ev.button == 1:
                    player.dash()
                elif not editor and ev.button == 3:
                    player.toggle_mini_mode(miniimg)

                elif editor:
                    if pal_x <= mx <= pal_x + palette_w and pal_y <= my <= pal_y + palette_h:
                        local_x = mx - pal_x - PALETTE_PADDING
                        local_y = my - pal_y - PALETTE_PADDING
                        cell_w = palette_tile_px + 4
                        gx_cell = local_x // cell_w
                        gy_cell = local_y // cell_w
                        idx = int(gy_cell * pal_cols + gx_cell)
                        if 0 <= idx < num_tiles:
                            selected_tile = palette_ids[idx]
                            continue

                    wx, wy = screen_to_world(mx, my, camx, camy)
                    gx = wx // TILE
                    gy = wy // TILE

                    if ev.button == 1 and grid.in_bounds(gx, gy):
                        grid.set_tile(gx, gy, selected_tile)
                        if selected_tile in COLLECTABLE_TILE_IDS:
                            add_collectable_at_cell(gx, gy)
                        elif selected_tile == KEY_TILE_ID:
                            try:
                                key_id = input("Enter key id for this key: ").strip()
                            except Exception:
                                key_id = None
                            add_key_for_pair((gx, gy), key_id)
                        mouse_painting = True

                    elif ev.button == 3 and grid.in_bounds(gx, gy):
                        if grid.get_tile(gx, gy) == KEY_TILE_ID:
                            remove_key_meta_by_cell(gx, gy)
                        grid.set_tile(gx, gy, 0)
                        remove_collectable_at_cell(gx, gy)
                        mouse_painting = True

                    if ev.button == 1 and grid.in_bounds(gx, gy):
                        if selected_tile == 55:
                            if grid.in_bounds(gx, gy + 1):
                                try:
                                    door_id = input("Enter door id for this door group: ").strip()
                                except Exception:
                                    door_id = None
                                grid.set_tile(gx, gy, 55)
                                grid.set_tile(gx, gy + 1, 65)
                                add_door_group([(gx, gy), (gx, gy + 1)], gid=door_id)
                                sync_key_door_objects()
                                mouse_painting = True
                                gid = door_id if door_id else generate_group_id([[gx, gy], [gx, gy + 1]])
                        elif selected_tile == 67:
                            try:
                                key_id = input("Enter key id for this key: ").strip()
                            except Exception:
                                key_id = None
                            add_key_for_pair((gx, gy), key_id)
                            mouse_painting = True

            if editor and ev.type == pygame.MOUSEMOTION and mouse_painting:
                mx, my = ev.pos
                wx, wy = screen_to_world(mx, my, camx, camy)
                gx = wx // TILE
                gy = wy // TILE
                buttons = pygame.mouse.get_pressed()
                if buttons[0] and grid.in_bounds(gx, gy):
                    grid.set_tile(gx, gy, selected_tile)
                    if selected_tile in COLLECTABLE_TILE_IDS:
                        add_collectable_at_cell(gx, gy)
                    elif selected_tile == KEY_TILE_ID:
                        try:
                            key_id = input("Enter key id for this key: ").strip()
                        except Exception:
                            key_id = None
                        add_key_for_pair((gx, gy), key_id)
                elif buttons[2] and grid.in_bounds(gx, gy):
                    if grid.get_tile(gx, gy) == KEY_TILE_ID:
                        remove_key_meta_by_cell(gx, gy)
                    grid.set_tile(gx, gy, 0)
                    remove_collectable_at_cell(gx, gy)

            if ev.type == pygame.MOUSEBUTTONUP:
                mouse_painting = False

            if ev.type == pygame.MOUSEWHEEL:
                selected_tile += ev.y
                if TILE_IMAGES:
                    min_id = min(TILE_IMAGES.keys())
                    max_id = max(TILE_IMAGES.keys())
                    selected_tile = int(max(min_id, min(max_id, selected_tile)))
                else:
                    selected_tile = clamp(selected_tile, 0, selected_tile)

        pressed = pygame.key.get_pressed()
        player.apply_input(pressed, w_pressed_now)
        death = player.update(dt, grid)

        for c in coins:
            c.update(dt)

        if death == "death":
            px = player.rect.centerx
            py = player.rect.centery
            emit_particles(px, py, 150, speed_spread=180, life_spread=1.8, color=(255, 80, 60), radius_range=(2, 5))
            shake_time = 0.6
            shake_mag = 14.0
            player.x, player.y = spawn_point
            player.vx = player.vy = 0.0
            player.rect.topleft = (int(player.x), int(player.y))
            player.climbing = False

        for c in coins[:]:
            if c.check_collect(player.rect):
                emit_particles(player.rect.centerx, player.rect.centery, 20, speed_spread=80, life_spread=1.0, color=(255, 220, 60), radius_range=(2, 4))

        key_cells = grid.get_all_cells_in_rect(player.rect)
        for (gx, gy) in key_cells:
            if grid.get_tile(gx, gy) == KEY_TILE_ID:
                collect_key_at_cell(gx, gy)

        target_camx = int(player.rect.centerx - render_w // 2)
        target_camy = int(player.rect.centery - render_h // 2)
        camx += (target_camx - camx) * 0.15
        camy += (target_camy - camy) * 0.15
        max_camx = max(0, grid.cols * TILE - render_w)
        max_camy = max(0, grid.rows * TILE - render_h)
        camx = clamp(camx, 0, max_camx)
        camy = clamp(camy, 0, max_camy)

        int_camx, int_camy = int(camx), int(camy)

        if shake_time > 0:
            shake_time = max(shake_time - dt, 0.0)
            offset = shake_mag * (shake_time / 0.6)
            max_offset = int(max(0, round(offset)))
            if max_offset == 0:
                shake_x, shake_y = 0, 0
            else:
                shake_x = random.randint(-max_offset, max_offset)
                shake_y = random.randint(-max_offset, max_offset)
        else:
            shake_x, shake_y = 0, 0

        grid.draw_visible(render_surf, int_camx, int_camy, render_w, render_h)

        for c in coins:
            c.draw(render_surf, int_camx, int_camy)
        
        for meta in KEYS_META:
            key_id = meta.get("id")
            cell = meta.get("cell", [])
            if len(cell) >= 2 and key_id not in RUNTIME_COLLECTED_KEYS:
                gx, gy = int(cell[0]), int(cell[1])
                if grid.in_bounds(gx, gy):
                    key_img = keyimg
                    if key_img:
                        cx = gx * TILE + TILE // 2 - int_camx
                        cy = gy * TILE + TILE // 2 - int_camy
                        draw_x = cx - key_img.get_width() // 2
                        draw_y = cy - key_img.get_height() // 2
                        render_surf.blit(key_img, (draw_x, draw_y))

        screen_img_x, screen_img_y, screen_img_w, screen_img_h = player.draw(render_surf, int_camx, int_camy)

        for p in particles:
            p.update(dt)
            p.draw(render_surf, int_camx, int_camy)
        particles = [p for p in particles if p.alive]

        if editor:
            for x in range(grid.cols + 1):
                xpix = x * TILE - int_camx
                pygame.draw.line(render_surf, (60, 60, 60), (xpix, -int_camy), (xpix, grid.rows * TILE - int_camy))
            for y in range(grid.rows + 1):
                ypix = y * TILE - int_camy
                pygame.draw.line(render_surf, (60, 60, 60), (-int_camx, ypix), (grid.cols * TILE - int_camx, ypix))

        scaled = pygame.transform.scale(render_surf, (W, H))
        SCREEN.blit(scaled, (shake_x, shake_y))

        y_off = 8
        if debug:
            s = bigfont.render("DEBUG MODE - NOCOLLIDE / FLY (U to toggle)", True, (255, 200, 50))
            SCREEN.blit(s, (8, y_off))
            y_off += s.get_height() + 6
        if editor:
            s = bigfont.render("EDITOR MODE (E to toggle) - Left:paint Right:erase R:rotate under mouse", True, (120, 200, 255))
            SCREEN.blit(s, (8, y_off))
            y_off += s.get_height() + 6

        tile_text = font.render(f"Selected tile: {selected_tile} | DEBUG: {debug} | EDITOR: {editor}", True, (220, 220, 220))
        SCREEN.blit(tile_text, (8, y_off))
        y_off += tile_text.get_height() + 6

        score_txt = bigfont.render(f"Score: {score}", True, (255, 220, 80))
        SCREEN.blit(score_txt, (W - score_txt.get_width() - 8, 8))

        if player.last_dash > 0.0:
            progress = clamp((DASH_COOLDOWN - player.last_dash) / DASH_COOLDOWN, 0.0, 1.0)
            BAR_W_UNSCALED = 80
            BAR_H_UNSCALED = 12
            bar_w = int(BAR_W_UNSCALED * ZOOM)
            bar_h = int(BAR_H_UNSCALED * ZOOM)
            bar_x_unscaled = screen_img_x + (screen_img_w // 2) - (BAR_W_UNSCALED // 2)
            bar_y_unscaled = screen_img_y - 20
            bar_x_screen = int(bar_x_unscaled * ZOOM) + shake_x
            bar_y_screen = int(bar_y_unscaled * ZOOM) + shake_y
            pygame.draw.rect(SCREEN, (50, 50, 50), (bar_x_screen, bar_y_screen, bar_w, bar_h))
            fill_width = int(bar_w * max(0, min(progress, 1)))
            pygame.draw.rect(SCREEN, (0, 200, 80), (bar_x_screen, bar_y_screen, fill_width, bar_h))
            pygame.draw.rect(SCREEN, (255, 255, 255), (bar_x_screen, bar_y_screen, bar_w, bar_h), 2)

        if editor:
            num_tiles = len(palette_ids)
            pal_cols = PALETTE_COLS
            pal_rows = (num_tiles + pal_cols - 1) // pal_cols
            palette_tile_px = int(TILE * ZOOM)
            cell_w = palette_tile_px + 4
            palette_w = pal_cols * cell_w + PALETTE_PADDING * 2
            palette_h = pal_rows * cell_w + PALETTE_PADDING * 2
            pal_x = W - palette_w - 8
            pal_y = 8
            pygame.draw.rect(SCREEN, (20, 20, 20), (pal_x, pal_y, palette_w, palette_h))
            pygame.draw.rect(SCREEN, (100, 100, 100), (pal_x, pal_y, palette_w, palette_h), 2)

            for i, tid in enumerate(palette_ids):
                gx = i % pal_cols
                gy = i // pal_cols
                px = pal_x + PALETTE_PADDING + gx * cell_w
                py = pal_y + PALETTE_PADDING + gy * cell_w
                img = TILE_IMAGES.get(tid)
                rot = per_tile_rotations.get(tid, 0)
                if img:
                    scaled_img = pygame.transform.scale(img, (palette_tile_px, palette_tile_px))
                    if rot != 0:
                        scaled_img = pygame.transform.rotate(scaled_img, rot)
                    rect = scaled_img.get_rect(center=(px + palette_tile_px // 2, py + palette_tile_px // 2))
                    SCREEN.blit(scaled_img, rect.topleft)
                else:
                    if tid == 0:
                        pygame.draw.line(SCREEN, (255, 0, 0), (px, py), (px + palette_tile_px, py + palette_tile_px), 2)
                        pygame.draw.line(SCREEN, (255, 0, 0), (px + palette_tile_px, py), (px, py + palette_tile_px), 2)
                    else:
                        pygame.draw.rect(SCREEN, (150, 50, 50), (px, py, palette_tile_px, palette_tile_px))
                if tid == selected_tile:
                    pygame.draw.rect(SCREEN, (255, 255, 255), (px - 2, py - 2, palette_tile_px + 4, palette_tile_px + 4), 2)
                text_surf = font.render(f"{tid} ({rot}°)", True, (200, 200, 200))
                SCREEN.blit(text_surf, (px, py + palette_tile_px + 2))

        pygame.display.flip()
        await asyncio.sleep(0)

asyncio.run(main())
pygame.quit()