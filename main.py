import math
import random
from pathlib import Path
 
import pygame
 
pygame.init()
W, H, FPS = 1920, 1080, 0
CW = 1          
RAYS = W // CW
FOV = 1.05
MAXD = 18
PROJ = (W / 2) / math.tan(FOV / 2)   
 
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Ретро-FPS — Гвинтівка")
clock = pygame.time.Clock()
ROOT = Path(__file__).parent
FONT = pygame.font.Font(None, 28)
SMALL = pygame.font.Font(None, 22)
BIG = pygame.font.Font(None, 78)
 
COLORS = {"1": (105, 105, 115), "2": (130, 80, 55), "3": (65, 100, 115),
          "4": (125, 65, 110), "D": (150, 115, 40)}
 
RAY_DELTA = [math.atan((2 * (r + .5) / RAYS - 1) * math.tan(FOV / 2)) for r in range(RAYS)]
RAY_COS = [math.cos(a) for a in RAY_DELTA]
 
BTN_START = pygame.Rect(W // 2 - 145, 500, 290, 58)
BTN_QUIT = pygame.Rect(W // 2 - 145, 600, 290, 58)
 
def load_img(path, size=None, alpha=True):
    try:
        s = pygame.image.load(str(ROOT / "textures" / path))
        s = s.convert_alpha() if alpha else s.convert()
        return pygame.transform.scale(s, size) if size else s
    except (pygame.error, FileNotFoundError):
        return None
 
 
def load_sound(path):
    try:
        return pygame.mixer.Sound(str(ROOT / "sounds" / path))
    except (pygame.error, FileNotFoundError):
        return None
 
 
class Enemy:
    def __init__(self, x, y, boss=False):
        self.x, self.y = x, y
        self.boss = boss
        self.maxhp = 300 if boss else 70
        self.hp = self.maxhp
        self.speed = .48 if boss else .75
        self.radius = .5 if boss else .3
        self.cool = random.uniform(.2, .8)
        self.dead = False
        self.hurt = 0
        self.alert = False    
 
    def update(self, p, world, dt):
        if self.dead:
            return False
        self.cool = max(0, self.cool - dt)
        self.hurt = max(0, self.hurt - dt)
        dx, dy = p.x - self.x, p.y - self.y
        d = math.hypot(dx, dy) or 1e-6
        sees = d < 10 and world.los(self.x, self.y, p.x, p.y)
        if sees:
            self.alert = True
        elif d > 14:
            self.alert = False
        enraged = self.boss and self.hp < self.maxhp * .5
        if self.alert and d > .85:
            sp = self.speed * (1.4 if enraged else 1)
            vx, vy = dx / d * sp * dt, dy / d * sp * dt
            if not world.blocked(self.x + vx, self.y):
                self.x += vx
            if not world.blocked(self.x, self.y + vy):
                self.y += vy
        if sees and d < (6 if self.boss else 4) and self.cool <= 0:
            self.cool = (.7 if enraged else 1.0) if self.boss else 1.35
            if random.random() < .8:
                p.hurt(16 if self.boss else 7)
            return True
        return False
 
    def damage(self, n):
        if self.dead:
            return
        self.hp -= n
        self.hurt = .12
        self.alert = True
        if self.hp <= 0:
            self.hp = 0
            self.dead = True
 
 
class World:
    def __init__(self):
        self.grid, self.enemies, self.pickups = [["1"]], [], []
        self.doors, self.boss, self.exit = {}, None, None
        self.w = self.h = 1
        self.start = (1.5, 1.5)
 
    @staticmethod
    def level_exists(n):
        return (ROOT / "levels" / f"level{n}.txt").exists()
 
    def load(self, n):
        path = ROOT / "levels" / f"level{n}.txt"
        if path.exists():
            text = path.read_text(encoding="utf-8")
        elif n == 1:
            text = DEFAULT_LEVEL
        else:
            raise FileNotFoundError(path)
        lines = [x.rstrip() for x in text.splitlines() if x.strip()]
        self.grid, self.enemies, self.pickups = [], [], []
        self.doors, self.boss, self.exit, self.start = {}, None, None, None
        self.h = len(lines)
        self.w = max(map(len, lines))
        for y, line in enumerate(lines):
            row = list(line.ljust(self.w, "1"))
            for x, c in enumerate(row):
                pos = (x + .5, y + .5)
                if c == "P":
                    self.start = pos
                    row[x] = "0"
                elif c == "E":
                    self.enemies.append(Enemy(*pos))
                    row[x] = "0"
                elif c == "B":
                    self.boss = Enemy(*pos, True)
                    self.enemies.append(self.boss)
                    row[x] = "0"
                elif c == "X":
                    self.exit = pos
                    row[x] = "0"
                elif c in "AH":
                    self.pickups.append({"p": pos, "kind": c, "taken": False})
                    row[x] = "0"
                elif c == "D":
                    self.doors[(x, y)] = False     
                    row[x] = "0"
            self.grid.append(row)
        if self.start is None:                       
            for y in range(self.h):
                for x in range(self.w):
                    if self.grid[y][x] == "0":
                        self.start = (x + .5, y + .5)
                        return
            self.start = (1.5, 1.5)
 
    def cell(self, ix, iy):
  
        if ix < 0 or iy < 0 or ix >= self.w or iy >= self.h:
            return "1"
        c = self.grid[iy][ix]
        if c != "0":
            return c if c in COLORS else "1"
        if self.doors.get((ix, iy)) is False:
            return "D"
        return None
 
    def wall(self, x, y):
        return self.cell(math.floor(x), math.floor(y)) is not None
 
    def blocked(self, x, y, r=.18):
        return (self.wall(x - r, y - r) or self.wall(x + r, y - r)
                or self.wall(x - r, y + r) or self.wall(x + r, y + r))
 
    def los(self, x0, y0, x1, y1):
   
        dx, dy = x1 - x0, y1 - y0
        n = int(math.hypot(dx, dy) / .1) + 1
        for i in range(1, n):
            t = i / n
            if self.wall(x0 + dx * t, y0 + dy * t):
                return False
        return True
 
    def near_door(self, x, y):
        best, bd = None, 1.5 ** 2
        for (dx, dy), opened in self.doors.items():
            if opened:
                continue
            d = (x - dx - .5) ** 2 + (y - dy - .5) ** 2
            if d < bd:
                best, bd = (dx, dy), d
        return best
 
    def cast(self, ox, oy, ang):
  
        rdx, rdy = math.cos(ang), math.sin(ang)
        mx, my = math.floor(ox), math.floor(oy)
        ddx = abs(1 / rdx) if rdx else 1e30
        ddy = abs(1 / rdy) if rdy else 1e30
        if rdx < 0:
            sx, sdx = -1, (ox - mx) * ddx
        else:
            sx, sdx = 1, (mx + 1 - ox) * ddx
        if rdy < 0:
            sy, sdy = -1, (oy - my) * ddy
        else:
            sy, sdy = 1, (my + 1 - oy) * ddy
        while True:
            if sdx < sdy:
                t = sdx
                sdx += ddx
                mx += sx
                side = 0
            else:
                t = sdy
                sdy += ddy
                my += sy
                side = 1
            if t > MAXD:
                return None
            c = self.cell(mx, my)
            if c:
                wx = oy + t * rdy if side == 0 else ox + t * rdx
                return t, side, wx - math.floor(wx), c, rdx, rdy
 
 
class Player:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.a = 0
        self.hp = 100
        self.ammo = 40
        self.weapon = "rifle"
        self.cool = 0
        self.anim = 0
        self.flash = 0
        self.kills = 0
        self.bob = 0
 
    def hurt(self, n):
        self.hp = max(0, self.hp - n)
        self.flash = .15
 
    def update(self, dt, world, keys, mouse_dx):
        self.a += mouse_dx * .0025 + (int(keys[pygame.K_RIGHT]) - int(keys[pygame.K_LEFT])) * 2.2 * dt
        f = int(keys[pygame.K_w] or keys[pygame.K_UP]) - int(keys[pygame.K_s] or keys[pygame.K_DOWN])
        s = int(keys[pygame.K_d]) - int(keys[pygame.K_a])
        moving = bool(f or s)
        length = math.hypot(f, s) or 1
        f /= length
        s /= length
        speed = 3 * (1.6 if keys[pygame.K_LSHIFT] else 1)
        dx = (math.cos(self.a) * f + math.cos(self.a + math.pi / 2) * s) * speed * dt
        dy = (math.sin(self.a) * f + math.sin(self.a + math.pi / 2) * s) * speed * dt
        if not world.blocked(self.x + dx, self.y):
            self.x += dx
        if not world.blocked(self.x, self.y + dy):
            self.y += dy
        if moving:
            self.bob += dt * (13 if keys[pygame.K_LSHIFT] else 9)
        self.cool = max(0, self.cool - dt)
        self.anim = max(0, self.anim - dt)
        self.flash = max(0, self.flash - dt)
 
    def attack(self):
   
        if self.cool > 0:
            return False
        if self.ammo <= 0:
            self.cool = .3
            return "empty"
        self.ammo -= 1
        self.cool = .22
        self.anim = .14
        return True
 
 
class Game:
    def __init__(self):
        self.state = "menu"
        self.level = 1
        self.world = World()
        self.running = True
        self.p = Player(1.5, 1.5)
        self.enemies = []
        self.total = 0
        self.cleared = False
        self.carry = None
        self.time = 0.0
        self.msg, self.msgtime = "", 0
        self.show_map = True
        self.show_fps = True
        self.snapshot = None
        self.depth = [MAXD] * RAYS
 
        self.menu_bg = load_img("menu/background.png", (W, H), False)
        self.logo = load_img("menu/logo.png")
        self.walltex = {str(i): load_img(f"walls/wall{i}.png") for i in range(1, 5)}
        self.walltex["D"] = load_img("walls/door.png")
        self.sky = load_img("sky/sky.png", (W, H // 2), False)
        self.floor = load_img("floor/ground.png", (W, H // 2), False)
        self.enemytex = load_img("enemies/enemy.png")
        self.bosstex = load_img("enemies/boss.png")
        self.pickuptex = {"H": load_img("pickups/health.png"), "A": load_img("pickups/ammo.png")}
        self.exittex = load_img("exit.png")
        self.weaptex = {"rifle": [load_img(f"weapons/rifle_{i}.png") for i in range(1, 4)]}
        self.snd = {n: load_sound(f"{n}.wav") for n in ("shoot", "hurt", "door", "empty", "death", "victory")}
 
    
        if not self.sky:
            self.sky = self.gradient(H // 2, (14, 18, 34), (46, 58, 90))
        if not self.floor:
            self.floor = self.gradient(H // 2, (20, 18, 16), (62, 56, 50))
        self.fog = pygame.Surface((CW, H))
        self.fog.fill((0, 0, 0))
        self.red = pygame.Surface((W, H), pygame.SRCALPHA)
        self.red.fill((180, 0, 0, 65))
        self.dim = pygame.Surface((W, H), pygame.SRCALPHA)
        self.dim.fill((0, 0, 0, 160))
 
    @staticmethod
    def gradient(h, top, bottom):
        s = pygame.Surface((W, h))
        for y in range(h):
            k = y / max(1, h - 1)
            pygame.draw.line(s, tuple(int(a + (b - a) * k) for a, b in zip(top, bottom)), (0, y), (W, y))
        return s
 
    def play(self, name):
        s = self.snd.get(name)
        if s:
            s.play()
 
    def say(self, text, t=1.5):
        self.msg, self.msgtime = text, t
 
    def capture(self, on):
        pygame.mouse.set_visible(not on)
        pygame.event.set_grab(on)
        if on:
            pygame.mouse.get_rel()      
 
    def start(self, n, carry=None):
        try:
            self.world.load(n)
        except (OSError, ValueError):
            self.state = "menu"
            return
        self.level = n
        self.p = Player(*self.world.start)
        if carry:
            self.p.hp, self.p.ammo, self.p.kills = carry
        else:
            self.time = 0.0
        self.carry = (self.p.hp, self.p.ammo, self.p.kills)
        self.enemies = self.world.enemies
        self.total = len(self.enemies)
        self.cleared = False
        self.say(f"РІВЕНЬ {n}: ЗНИЩ УСІХ ВОРОГІВ" + (" І БОСА" if self.world.boss else ""), 2.5)
        self.p.cool = .3                 
        self.state = "game"
        self.capture(True)
 
    def finish_level(self):
        if World.level_exists(self.level + 1):
            self.start(self.level + 1, carry=(self.p.hp, self.p.ammo, self.p.kills))
        else:
            self.state = "victory"
            self.play("victory")
            self.capture(False)
         
            
 
    def attack(self):
        st = self.p.attack()
        if st == "empty":
            self.play("empty")
            self.say("НЕМАЄ НАБОЇВ", .8)
            return
        if not st:
            return
        self.play("shoot")
        target, best = None, 10
        for e in self.enemies:
            if e.dead:
                continue
            dx, dy = e.x - self.p.x, e.y - self.p.y
            d = math.hypot(dx, dy)
            if d >= best:
                continue
            delta = (math.atan2(dy, dx) - self.p.a + math.pi) % (2 * math.pi) - math.pi
            if abs(delta) > math.atan2(e.radius, d) + .02:
                continue
            if not self.world.los(self.p.x, self.p.y, e.x, e.y):
                continue
            target, best = e, d
        if target:
            target.damage(38)
            if target.dead:
                self.p.kills += 1
                self.play("death")
 
    def open_door(self):
        d = self.world.near_door(self.p.x, self.p.y)
        if d:
            self.world.doors[d] = True
            self.play("door")
            self.say("ДВЕРІ ВІДЧИНЕНО", 1)
 
    def pause(self):
        self.snapshot = screen.copy()
        self.state = "pause"
        self.capture(False)
 
    def events(self):
        lost = getattr(pygame, "WINDOWFOCUSLOST", None)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.running = False
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
                pygame.display.toggle_fullscreen()
            elif self.state == "menu":
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_RETURN:
                        self.start(1)
                    elif e.key == pygame.K_ESCAPE:
                        self.running = False
                elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    if BTN_START.collidepoint(e.pos):
                        self.start(1)
                    elif BTN_QUIT.collidepoint(e.pos):
                        self.running = False
            elif self.state == "game":
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        self.pause()
                    elif e.key == pygame.K_e:
                        self.open_door()
                    elif e.key == pygame.K_TAB:
                        self.show_map = not self.show_map
                    elif e.key == pygame.K_F3:
                        self.show_fps = not self.show_fps
                elif lost is not None and e.type == lost:
                    self.pause()
            elif self.state == "pause" and e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.state = "game"
                    self.capture(True)
                elif e.key == pygame.K_m:
                    self.state = "menu"
            elif self.state in ("dead", "victory") and e.type == pygame.KEYDOWN:
                if e.key == pygame.K_RETURN:
                    self.state = "menu"
                elif e.key == pygame.K_r and self.state == "dead":
                    self.start(self.level, carry=self.carry)
 
    def separate_enemies(self):
        alive = [e for e in self.enemies if not e.dead]
        for i, a in enumerate(alive):
            for b in alive[i + 1:]:
                dx, dy = b.x - a.x, b.y - a.y
                d = math.hypot(dx, dy)
                m = a.radius + b.radius
                if 0 < d < m:
                    push = (m - d) / 2
                    nx, ny = dx / d * push, dy / d * push
                    for en, sgn in ((a, -1), (b, 1)):
                        if not self.world.blocked(en.x + nx * sgn, en.y):
                            en.x += nx * sgn
                        if not self.world.blocked(en.x, en.y + ny * sgn):
                            en.y += ny * sgn
 
    def update(self, dt):
        if self.state != "game":
            return
        self.time += dt
        keys = pygame.key.get_pressed()
        mdx = pygame.mouse.get_rel()[0] if pygame.mouse.get_focused() else 0
        mdx = max(-150, min(150, mdx))
        self.p.update(dt, self.world, keys, mdx)
        if pygame.mouse.get_pressed()[0] or keys[pygame.K_SPACE] or keys[pygame.K_f]:
            self.attack()
        hp_before = self.p.hp
        for e in self.enemies:
            e.update(self.p, self.world, dt)
        if self.p.hp < hp_before:
            self.play("hurt")
        self.separate_enemies()
 
        for it in self.world.pickups:
            if it["taken"]:
                continue
            x, y = it["p"]
            if (self.p.x - x) ** 2 + (self.p.y - y) ** 2 < .5 ** 2:
                if it["kind"] == "H" and self.p.hp < 100:
                    self.p.hp = min(100, self.p.hp + 30)
                    it["taken"] = True
                    self.say("+30 ЗДОРОВ’Я", 1)
                elif it["kind"] == "A":
                    self.p.ammo += 15
                    it["taken"] = True
                    self.say("+15 НАБОЇВ", 1)
                if it["taken"]:
                    self.play("pickup")
        self.msgtime = max(0, self.msgtime - dt)
 
        if self.p.hp <= 0:
            self.state = "dead"
            self.capture(False)
            return
 
        if not self.cleared and all(e.dead for e in self.enemies):
            self.cleared = True
            if self.world.exit:
                self.say("ВОРОГІВ ЗНИЩЕНО — ЙДИ ДО ВИХОДУ", 3)
            elif self.enemies:
                self.finish_level()
                return
        ex = self.world.exit
        if ex and (self.p.x - ex[0]) ** 2 + (self.p.y - ex[1]) ** 2 < .6 ** 2:
            if self.cleared:
                self.finish_level()
            else:
                self.say("СПОЧАТКУ ЗНИЩ УСІХ ВОРОГІВ", 1)
 
    
    def render_world(self):
        screen.blit(self.sky, (0, 0))
        screen.blit(self.floor, (0, H // 2))
        depth = [MAXD] * RAYS
        p, half = self.p, H // 2
        for r in range(RAYS):
            hit = self.world.cast(p.x, p.y, p.a + RAY_DELTA[r])
            if not hit:
                continue
            t, side, wallx, c, rdx, rdy = hit
            d = max(.05, t * RAY_COS[r])
            depth[r] = d
            wh = int(H / d)
            top = half - wh // 2
            shade = max(.2, 1 - d / MAXD) * (.72 if side else 1)
            x = r * CW
            tex = self.walltex.get(c)
            if tex:
                tw, th = tex.get_size()
                tx = int(wallx * tw)
                if (side == 0 and rdx > 0) or (side == 1 and rdy < 0):
                    tx = tw - 1 - tx
                tx = max(0, min(tw - 1, tx))
                if wh > H:                 
                    sh = max(1, int(th * H / wh))
                    sy = (th - sh) // 2
                    strip, dh, dtop = tex.subsurface((tx, sy, 1, sh)), H, 0
                else:
                    strip, dh, dtop = tex.subsurface((tx, 0, 1, th)), max(1, wh), top
                screen.blit(pygame.transform.scale(strip, (CW, dh)), (x, dtop))
                a = int(255 * (1 - shade))
                if a > 0:
                    self.fog.set_alpha(a)
                    screen.blit(self.fog, (x, dtop), (0, 0, CW, dh))
            else:
                col = tuple(int(v * shade) for v in COLORS[c])
                y0, y1 = max(0, top), min(H, top + wh)
                pygame.draw.rect(screen, col, (x, y0, CW, y1 - y0))
        self.depth = depth
 
    def project(self, x, y):
        dx, dy = x - self.p.x, y - self.p.y
        ca, sa = math.cos(self.p.a), math.sin(self.p.a)
        return dx * ca + dy * sa, -dx * sa + dy * ca
 
    def draw_sprite(self, fwd, side, scale, ratio, zoff, make, tint=None):
       
        size = min(int(H / fwd * scale), H * 2)
        if size < 3:
            return
        sw, sh = max(0.5, int(size * ratio)), size
        sx = int(W / 2 + side / fwd * PROJ)
        left = sx - sw // 2
        x0, x1 = max(0, left), min(W, left + sw)
        if x0 >= x1:
            return
        top = H // 2 - sh // 2 + int(zoff * sh)
        surf = make(sw, sh)
        if tint:
            surf.fill(tint, special_flags=pygame.BLEND_RGB_ADD)
        v = int(255 * max(.3, 1 - fwd / MAXD))
        surf.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
        x = x0
        while x < x1:
            w = min(CW, x1 - x)
            if fwd < self.depth[min(RAYS - 1, x // CW)] + .25:
                screen.blit(surf, (x, top), (x - left, 0, w, sh))
            x += w
 
    def render_sprites(self):
        items = []
        for e in self.enemies:
            if not e.dead:
                items.append((math.hypot(e.x - self.p.x, e.y - self.p.y), "enemy", e))
        for it in self.world.pickups:
            if not it["taken"]:
                items.append((math.hypot(it["p"][0] - self.p.x, it["p"][1] - self.p.y), "pickup", it))
        if self.world.exit:
            ex = self.world.exit
            items.append((math.hypot(ex[0] - self.p.x, ex[1] - self.p.y), "exit", ex))
        items.sort(key=lambda i: i[0], reverse=True)
        for _, kind, obj in items:
            if kind == "enemy":
                fwd, side = self.project(obj.x, obj.y)
            elif kind == "pickup":
                fwd, side = self.project(*obj["p"])
            else:
                fwd, side = self.project(*obj)
            if fwd <= .15 or abs(side) > fwd * math.tan(FOV / 2) * 1.6:
                continue
            if kind == "enemy":
                self.draw_sprite(fwd, side, 2.0 if obj.boss else .85, 2 / 3, 0,
                                 lambda w, h, e=obj: self.enemy_surface(e, w, h),
                                 (110, 35, 35) if obj.hurt > 0 else None)
            elif kind == "pickup":
                self.draw_sprite(fwd, side, .35, 1, .3,
                                 lambda w, h, k=obj["kind"]: self.pickup_surface(k, w, h))
            else:
                self.draw_sprite(fwd, side, .9, .5, 0, lambda w, h: self.exit_surface(w, h))
 
    def enemy_surface(self, e, w, h):
        tex = self.bosstex if e.boss else self.enemytex
        if tex:
            return pygame.transform.scale(tex, (w, h))
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        body = (130, 35, 150) if e.boss else ((255, 100, 80) if e.hurt > 0 else (155, 48, 48))
        pygame.draw.rect(s, body, (0, 0, w, h))
        ey, ew = h // 3, max(3, h // 12)
        pygame.draw.rect(s, (255, 220, 80), (w // 2 - w // 4, ey, ew, ew))
        pygame.draw.rect(s, (255, 220, 80), (w // 2 + w // 8, ey, ew, ew))
        return s
 
    def pickup_surface(self, kind, w, h):
        tex = self.pickuptex.get(kind)
        if tex:
            return pygame.transform.scale(tex, (w, h))
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        if kind == "H":
            pygame.draw.rect(s, (235, 235, 235), (0, 0, w, h))
            t = max(2, w // 5)
            pygame.draw.rect(s, (200, 30, 30), (w // 2 - t // 2, h // 5, t, h * 3 // 5))
            pygame.draw.rect(s, (200, 30, 30), (w // 5, h // 2 - t // 2, w * 3 // 5, t))
        else:
            pygame.draw.rect(s, (200, 160, 40), (0, 0, w, h))
            pygame.draw.rect(s, (90, 70, 20), (0, 0, w, h), max(1, w // 12))
            for i in range(3):
                pygame.draw.rect(s, (60, 45, 15), (w // 5 + i * w // 3, h // 4, max(2, w // 8), h // 2))
        return s
 
    def exit_surface(self, w, h):
        if self.exittex:
            return pygame.transform.scale(self.exittex, (w, h))
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        col = (60, 220, 90) if self.cleared else (200, 50, 50)
        pygame.draw.rect(s, col + (150,), (0, 0, w, h))
        pygame.draw.rect(s, col, (0, 0, w, h), max(2, w // 10))
        return s
 
    def render_boss_bar(self):
        b = self.world.boss
        if b and not b.dead and b.alert:
            pygame.draw.rect(screen, (45, 20, 20), (W // 2 - 120, 15, 240, 15))
            pygame.draw.rect(screen, (190, 35, 45), (W // 2 - 120, 15, int(240 * b.hp / b.maxhp), 15))
            pygame.draw.rect(screen, (230, 230, 230), (W // 2 - 120, 15, 240, 15), 1)
            self.text("БОС", SMALL, 33)
 
    def render_weapon(self):
        frames = self.weaptex[self.p.weapon]
        frame = 0 if self.p.anim <= 0 else (1 if self.p.anim > .08 else 2)
        ox = int(math.sin(self.p.bob) * 8)
        oy = int(abs(math.cos(self.p.bob)) * 6) + int(self.p.anim * 60)
        tex = frames[frame]
        if tex:
            screen.blit(tex, (W // 2 - tex.get_width() // 2 + ox + 30   ,H - tex.get_height() + oy))
            return
        cx, by = W // 2 + ox, H - 12 + oy
        if self.p.weapon == "rifle":
            pygame.draw.rect(screen, (48, 48, 52), (cx - 32, by - 120, 64, 120))
            pygame.draw.rect(screen, (100, 100, 105), (cx - 10, by - 200, 20, 100))
            if self.p.anim:
                pygame.draw.polygon(screen, (255, 190, 60),
                                    [(cx, by - 230), (cx - 22, by - 190), (cx, by - 202), (cx + 22, by - 190)])
 
    def render_minimap(self):
        R, S = 8, 10
        size = (2 * R + 1) * S
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 140))
        px, py = int(self.p.x), int(self.p.y)
        for cy in range(py - R, py + R + 1):
            for cx in range(px - R, px + R + 1):
                c = self.world.cell(cx, cy)
                if c:
                    col = (200, 160, 50) if c == "D" else (110, 110, 125)
                    pygame.draw.rect(surf, col, ((cx - px + R) * S, (cy - py + R) * S, S - 1, S - 1))
        def pos(x, y):
            return int((x - px + R) * S), int((y - py + R) * S)
        if self.world.exit:
            ex, ey = pos(*self.world.exit)
            pygame.draw.circle(surf, (60, 220, 90) if self.cleared else (200, 50, 50), (ex, ey), 4)
        for e in self.enemies:
            if not e.dead:
                ex, ey = pos(e.x, e.y)
                pygame.draw.circle(surf, (230, 60, 60), (ex, ey), 4 if e.boss else 3)
        ppx, ppy = pos(self.p.x, self.p.y)
        pygame.draw.circle(surf, (80, 230, 110), (ppx, ppy), 3)
        pygame.draw.line(surf, (80, 230, 110), (ppx, ppy),
                         (ppx + int(math.cos(self.p.a) * 9), ppy + int(math.sin(self.p.a) * 9)), 2)
        pygame.draw.rect(surf, (200, 200, 210), (0, 0, size, size), 1)
        screen.blit(surf, (10, 10))
 
    def text(self, s, font, y, color=(240, 240, 240)):
        surf = font.render(s, True, color)
        screen.blit(surf, (W // 2 - surf.get_width() // 2, y))
 
    def render_hud(self):
        pygame.draw.rect(screen, (12, 12, 15), (0, H - 34, W, 34))
        alive = sum(1 for e in self.enemies if not e.dead)
        parts = [(f"ЗДОРОВ’Я {self.p.hp}", (255, 90, 90) if self.p.hp < 30 else (240, 240, 240)),
                 (f"НАБОЇ {self.p.ammo}", (255, 190, 80) if self.p.ammo < 5 else (240, 240, 240)),
                 ("ГВИНТІВКА", (240, 240, 240)),
                 (f"ВОРОГИ {alive}/{self.total}", (240, 240, 240)),
                 (f"РІВЕНЬ {self.level}", (240, 240, 240))]
        x = 12
        for label, col in parts:
            surf = FONT.render(label, True, col)
            screen.blit(surf, (x, H - 29))
            x += surf.get_width() + 32
        cx, cy = W // 2, H // 2
        pygame.draw.line(screen, (240, 240, 240), (cx - 7, cy), (cx + 7, cy), 2)
        pygame.draw.line(screen, (240, 240, 240), (cx, cy - 7), (cx, cy + 7), 2)
 
    def draw(self):
        if self.state == "menu":
            if self.menu_bg:
                screen.blit(self.menu_bg, (0, 0))
            else:
                screen.fill((18, 20, 30))
            if self.logo:
                screen.blit(self.logo, (W // 2 - self.logo.get_width() // 2, 200))
            else:
                self.text("РЕТРО-FPS", BIG, 300)
            mp = pygame.mouse.get_pos()
            for rect, label in ((BTN_START, "ПОЧАТИ ГРУ"), (BTN_QUIT, "ВИХІД")):
                hover = rect.collidepoint(mp)
                pygame.draw.rect(screen, (66, 66, 78) if hover else (42, 42, 48), rect)
                pygame.draw.rect(screen, (240, 240, 250) if hover else (180, 180, 190), rect, 2)
                self.text(label, FONT, rect.y + 17)
            self.text("WASD — рух | Shift — біг | Миша — огляд | ЛКМ / ПРОБІЛ / F — стріляти", FONT, 800)
            self.text("E — двері | Tab — міні-карта | F3 — FPS | F11 — повний екран | ESC — пауза", FONT, 870)
        elif self.state == "game":
            self.render_world()
            self.render_sprites()
            self.render_boss_bar()
            self.render_weapon()
            self.render_hud()
            if self.p.flash:
                screen.blit(self.red, (0, 0))
            if self.msgtime > 0:
                self.text(self.msg, FONT, H // 2 + 60, (255, 235, 140))
            elif self.world.near_door(self.p.x, self.p.y):
                self.text("E — відчинити двері", FONT, H // 2 + 60, (255, 235, 140))
            if self.show_map:
                self.render_minimap()
            if self.show_fps:
                screen.blit(SMALL.render(f"{clock.get_fps():.0f} FPS", True, (200, 255, 200)), (W - 80, 8))
        elif self.state == "pause":
            if self.snapshot:
                screen.blit(self.snapshot, (0, 0))
            screen.blit(self.dim, (0, 0))
            self.text("ПАУЗА", BIG, 190)
            self.text("ESC — продовжити | M — головне меню", FONT, 285)
        else:
            screen.fill((12, 13, 18))
            mins, secs = divmod(int(self.time), 60)
            stats = f"Рівень: {self.level}   Знищено ворогів: {self.p.kills}   Час: {mins:02d}:{secs:02d}"
            if self.state == "dead":
                self.text("ТИ ЗАГИНУВ", BIG, 190)
                self.text("R — спробувати знову | ENTER — меню", FONT, 285)
            else:
                self.text("ПЕРЕМОГА!", BIG, 190)
                self.text("Усіх ворогів знищено! Натисни ENTER для меню", FONT, 285)
            self.text(stats, FONT, 325, (200, 200, 210))
 
 
def main():
    game = Game()
    while game.running:
        dt = min(clock.tick() / 1000, .04)
        game.events()
        game.update(dt)
        game.draw()
        pygame.display.flip()
    pygame.quit()
 
 
if __name__ == "__main__":
    main()