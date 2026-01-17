import pygame, json, os, asyncio, random, math, platform
IS_MOBILE = platform.system() == "Emscripten" or hasattr(pygame, "FINGERDOWN")
pygame.init()
Info = pygame.display.Info()
W, H = 1920, 1080
w = pygame.display.set_mode((W, H))
pygame.display.set_caption('Tower Defense')
running = True
clock = pygame.time.Clock()
maxfps = 60
gui = 0
font1 = pygame.font.SysFont(None, 50)
font2 = pygame.font.SysFont(None, 35)
font3 = pygame.font.SysFont(None, 20)
selected = None
mx, my = 0, 0
cache = {}
with open("templates.json", "r") as f:
    full = json.load(f)
    towerTemp = full["towers"]
    enemyTemp = full["enemies"]
    route = full["route"]

class Base:
    def __init__(self):
        self.maxhp = 300
        self.hp = self.maxhp

    def decrease_hp(self, amount):
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            game.game_over()

    def increase_hp(self, amount):
        self.hp += amount
        if self.hp > self.maxhp:
            self.hp = self.maxhp

class BlastProjectile:
    def __init__(self, targetx, targety, currentx, currenty, blastradius, damage, color, size, parent):
        self.target = (targetx, targety)
        self.pos = [currentx, currenty]
        self.col = color
        self.radius = blastradius
        self.dmg = damage
        self.size = size
        self.dx = targetx - self.pos[0]
        self.dy = targety - self.pos[1]
        self.rect = pygame.Rect(currentx, currenty, size, size)
        self.parent = parent
        self.speed = 500
        length = (self.dx**2 + self.dy**2)**0.5
        if length != 0:
            self.dir = (self.dx/length, self.dy/length)
        else:
            self.dir = (0, 0)

    def boom(self):
        obj = [["#ffffff", self.pos, self.radius], 0.2]
        temporary.append(obj)
        givendmg = 0
        for i in enemies[:]:
            dx, dy = self.pos[0] - i.rect.centerx, self.pos[1] - i.rect.centery
            dist = (dx**2+dy**2)**0.5
            if dist <= self.radius:
                i.take_damage(self.dmg)
                givendmg += self.dmg
        self.parent.totaldmg += givendmg
        projectiles.remove(self)

    def update(self, dt):
        self.pos[0] += self.dir[0] * self.speed * dt
        self.pos[1] += self.dir[1] * self.speed * dt
        self.rect.center = self.pos
        self.dx = self.target[0] - self.pos[0]
        self.dy = self.target[1] - self.pos[1]
        length = (self.dx**2 + self.dy**2)**0.5
        if length < self.speed*dt:
            self.boom()

class Game:
    def __init__(self):
        global gui, route
        self.map = [(W/4, H), (W/4, H/5), (W/4*3, H/5), (W/4*3, H/5*4), (W/2, H/5*4), (W/2, H/5*2), (W, H/5*2)]
        self.money = 550
        self.text_cache = {}
        self.waittime = 0
        self.quant = 0
        self.wave = 0
        self.ev = -1
        self.end = False
        self.skip = False
        self.candrawskip = False
        self.last_tap_time = 0
        self.double_tap_threshold = 0.3  # Seconds
        self.touch_start_y = 0
        self.speed_multiplier = 1
        self.speed_button_rect = pygame.Rect(W - 150, H - 80, 120, 60)
        self.targeting_button_rect = pygame.Rect(W/8, (H/5)*3.5, (W/4)*3, (H/16))
        self.tower_limit = 20  # Set your desired max towers here
        self.current_towers = 0

    def get_ev(self):
        tmp = route[f"wave{self.wave}"]
        if self.ev >= 0:
            if isinstance(tmp[self.ev], dict):
                return "spawn"
            elif isinstance(tmp[self.ev], list):
                return "end"
        elif self.ev == -1:
            return "spawn"

    def next_ev(self, dt):
        if self.end:
            global gui
            gui = 4
            return
        if self.waittime <= 0:
            if self.ev == -1:
                if self.wave > 0:
                    prev_wave_data = route[f"wave{self.wave}"]
                    self.inc_money(prev_wave_data[-1][1])
                    for t in towers:
                        if hasattr(t, 'attributes') and t.attributes.get("money_tower", False):
                            # Gelir olarak 'damage' değerini kullanıyoruz
                            self.inc_money(t.dmg)
                            
                            # Görsel efekt: Kulenin üzerinde yeşil bir halka çıkar
                            obj = [["#00ff00", t.rect.center, 40], 0.6]
                            temporary.append(obj)
                self.wave += 1
                current_wave_key = f"wave{self.wave}"
                if current_wave_key not in route:
                    self.end = True
                    return
                self.ev = 0
                wave_data = route[current_wave_key]
                self.quant = wave_data[self.ev]["quantity"]
                return 
            wave_data = route[f"wave{self.wave}"]
            current_event = wave_data[self.ev]
            if isinstance(current_event, dict):
                self.candrawskip = False
                if self.quant > 0:
                    enemies.append(Enemy(current_event["name"]))
                    self.waittime = current_event["cooldown"]
                    self.quant -= 1
                else:
                    self.ev += 1
                    next_event = wave_data[self.ev]
                    if isinstance(next_event, dict):
                        self.quant = next_event["quantity"]
            elif isinstance(current_event, list):
                self.candrawskip = True
                self.waittime = current_event[0]
                self.ev = -1
        else:
            self.waittime -= dt

    def skip_wave(self):
        if self.candrawskip:
            self.waittime = 0

    def game_over(self):
        global gui
        gui = 5
        pygame.quit()

    def inc_money(self, amount):
        self.money += amount

    def dec_money(self, amount):
        self.money -= amount

    def cached_draw(self, screen, font, text, color, position, center=False):
        text_str = str(text)
        key = (text_str, color, id(font))
        if key not in self.text_cache:
            self.text_cache[key] = font.render(text_str, True, color).convert_alpha()
        surf = self.text_cache[key]
        if center:
            rect = surf.get_rect(center=position.center if hasattr(position, 'center') else position)
        else:
            rect = position
        return screen.blit(surf, rect)

game = Game()
base = Base()

class Enemy:
    def __init__(self, enemy):
        if enemy in enemyTemp:
            full = enemyTemp[enemy]
            self.maxhp = full["maxhealth"]
            self.col = full["color"]
            self.speed = full["speed"]
            self.hp = self.maxhp
            self.size = full["size"]
            self.name = enemy
            self.idx = 0
            self.x, self.y = game.map[0][0], game.map[0][1]
            self.rect = pygame.Rect(self.x - self.size, self.y - self.size, self.size, self.size)
            self.nt = False
            self.process = 0
            self.hidden = full.get("hidden", False)
            self.death_spawn_quantity = 1
            self.attributes = full.get("attributes", {})
            self.spawn_timer = 0
            self.spawn_queue = 0
            self.spawn_delay_timer = 0
            if "spawn" in self.attributes:
                self.spawn_timer = self.attributes["spawn"]["cooldown"]
            if "quantity" in self.attributes:
                self.death_spawn_quantity = self.attributes["quantity"]
        else:
            raise ValueError(f"\"{enemy}\" enemy is not in enemy templates.")

    def step(self, dt):
        if "spawn" in self.attributes:
            spawn_data = self.attributes["spawn"]
            self.spawn_timer -= dt
            if self.spawn_timer <= 0:
                self.spawn_queue = spawn_data["quantity"]
                self.spawn_timer = spawn_data["cooldown"]
            if self.spawn_queue > 0:
                self.spawn_delay_timer -= dt
                if self.spawn_delay_timer <= 0:
                    new_enemy = Enemy(spawn_data["name"])
                    new_enemy.x, new_enemy.y = self.x, self.y
                    new_enemy.idx = self.idx
                    new_enemy.process = self.process
                    enemies.append(new_enemy)
                    self.spawn_queue -= 1
                    self.spawn_delay_timer = spawn_data["spawnrate"]

        if self.nt:
            self.idx += 1
            self.nt = False
        if self.idx + 1 > len(game.map):
            if self in enemies: enemies.remove(self)
            base.decrease_hp(self.hp)
            return
        
        goalx, goaly = game.map[self.idx]
        dx, dy = goalx - self.x, goaly - self.y
        distance = (dx**2 + dy**2)**0.5
        move = self.speed * dt
        if distance <= move:
            self.x = goalx
            self.y = goaly
            self.process += distance
            self.nt = True
        else:
            dx, dy = dx / distance * move, dy / distance * move
            self.x += dx
            self.y += dy
            self.process += move
        self.rect = pygame.Rect(self.x - self.size/2, self.y - self.size/2, self.size, self.size)
        pygame.draw.circle(w, self.col, (self.rect.centerx, self.rect.centery), self.size/2)

    def take_damage(self, amount):
        namount = amount
        if amount > self.hp:
            namount = self.hp
        self.hp -= namount
        game.inc_money(namount)
        
        if self.hp <= 0:
            if "death_spawn" in self.attributes:
                spawn_list = self.attributes["death_spawn"]
                random_enemy_name = random.choice(spawn_list)
                new_enemy = Enemy(random_enemy_name)
                new_enemy.x, new_enemy.y = self.x, self.y
                new_enemy.idx = self.idx
                new_enemy.process = self.process
                enemies.append(new_enemy)
            if "quantity" in self.attributes:
                for i in range(self.death_spawn_quantity):
                    new_enemy = Enemy("Goo")
                    new_enemy.x, new_enemy.y = self.x, self.y
                    new_enemy.idx = self.idx
                    new_enemy.process = self.process
                    enemies.append(new_enemy)
            if self in enemies:
                enemies.remove(self)

phtower = 0
placing_tower = False

class placeholderTower:
    def __init__(self, tower):
        global gui
        self.size = 50
        if tower in towerTemp:
            self.name = tower
            full = towerTemp[tower]
            self.col = full["color"]
            self.cost = full["cost"]
            self.range = full["range"]
            self.rect = pygame.Rect(0, 0, self.size, self.size)
            gui = 2
        else:
            raise ValueError(f"\"{tower}\" tower not in tower templates.")

    def update(self):
        mpos = pygame.mouse.get_pos()
        self.rect.center = mpos

class Tower:
    def __init__(self, x, y, tower):
        self.size = 50
        if tower in towerTemp:
            self.x = x
            self.y = y
            self.name = tower
            full = towerTemp[tower]
            self.col = full["color"]
            self.dmg = full["damage"]
            self.frate = full["firerate"]
            self.range = full["range"]
            self.rect = pygame.Rect(0, 0, self.size, self.size)
            self.rect.center = (x, y)
            self.waittime = 0
            self.mode = full.get("mode", "first")
            self.upgs = full["upgrades"]
            self.attributes = full.get("attributes", {})
            self.hidden = bool(self.attributes.get("detection", False))
            self.dmgtype = self.attributes.get("damage_type", "normal")
            self.radius = full.get("blastradius", None)
            self.lvl = 0
            self.nextupgradeprice = self.upgs[self.lvl]["price"]
            self.totaldmg = 0
            self.cost = full["cost"]
            self.sellprice = self.cost*0.7
            self.maxlvl = len(self.upgs)
            self.aoeangle = full.get("aoeangle", 0)
            self.angle = 0  # Kulenin o an baktığı yön
            self.is_money_tower = self.attributes.get("money_tower", False)
        else:
            raise ValueError(f"\"{tower}\" tower not in tower templates.")

    def upgrade(self):
        mustupgrade = self.upgs[self.lvl]
        if game.money < self.nextupgradeprice:
            return
        nf = mustupgrade.get("firerate", False)
        nd = mustupgrade.get("damage", False)
        nr = mustupgrade.get("range", False)
        nh = bool(mustupgrade.get("detection", False))
        game.dec_money(mustupgrade["price"])
        if nd > 0:
            self.dmg = nd
        if nr > 0:
            self.range = nr
        if nf > 0:
            self.frate = nf
        if "detection" in mustupgrade:
            self.hidden = mustupgrade["detection"]
        self.lvl += 1
        self.sellprice += int(mustupgrade["price"]*0.7)
        if self.lvl != self.maxlvl:
            self.nextupgradeprice = self.upgs[self.lvl]["price"]

    def get_in_range(self, enemies):
        objs = []
        for i in enemies:
            dx, dy = self.x - i.x, self.y - i.y
            dist = (dx**2+dy**2)**0.5
            if dist <= self.range:
                if not i.hidden:
                    objs.append([i, dist])
                elif self.hidden:
                    objs.append([i, dist])
        return objs

    def update(self, dt, enemies):
        if self.waittime > 0:
            self.waittime -= dt
            
        elist = self.get_in_range(enemies)
        
        if len(elist) > 0:
            # Bakılacak hedefi seç (Açı için şart)
            if self.mode == "first":
                theone_data = max(elist, key=lambda x: x[0].process)
            elif self.mode == "strongest":
                theone_data = max(elist, key=lambda x: x[0].maxhp)
            
            target_enemy = theone_data[0]

            # Açı güncelleme (Pygame koordinatları için -dy)
            dx = target_enemy.x - self.x
            dy = target_enemy.y - self.y
            self.angle = math.degrees(math.atan2(-dy, dx))

            if self.waittime <= 0:
                # --- AOE Vuruş ---
                if self.aoeangle > 0:
                    for e_data in elist:
                        enemy = e_data[0]
                        edx = enemy.x - self.x
                        edy = enemy.y - self.y
                        e_angle = math.degrees(math.atan2(-edy, edx))
                        
                        # Açı farkı normalleştirme
                        diff = (e_angle - self.angle + 180) % 360 - 180
                        if abs(diff) <= self.aoeangle / 2:
                            enemy.take_damage(self.dmg)
                            self.totaldmg += self.dmg
                    self.waittime = self.frate # Cooldown başlat
                
                # --- Normal Tekli Vuruş ---
                elif self.dmgtype == "normal":
                    target_enemy.take_damage(self.dmg)
                    self.totaldmg += self.dmg
                    self.waittime = self.frate
                
                # --- Splash (Roket) Vuruş ---
                elif self.dmgtype == "splash":
                    projectiles.append(BlastProjectile(
                        target_enemy.x, target_enemy.y, 
                        self.x, self.y, 
                        self.radius, self.dmg, 
                        "#00ffff", 25, self
                    ))
                    self.waittime = self.frate

    def sell(self):
        game.inc_money(self.sellprice)
        towers.remove(self)

towers = []
enemies = []
projectiles = []
temporary = []
shop_button_rect = pygame.Rect(W/128, H-H/9, W/5.5, H/10)
skip_wave_rect = pygame.Rect(0,0,W/19.2,H/10.8)
skip_wave_rect.center=(W/128*10,H/72*7) 
tower_cancel_rect = pygame.Rect(W/10*9, H-H/9, W/19.2, H/10.8)
shop_rect = pygame.Rect(W/2-((W/3)*2)/2, H/2-(H/4*3)/2, W/3*2, H/4*3)
shop_surf = pygame.Surface((int(W/3*2), int(H/4*3)))
SW, SH = shop_surf.get_width(), shop_surf.get_height()
shopy = 0
shopmaxy = len(towerTemp)*(SH/5)-((SH/6)*4)
shop_close_button_rect = pygame.rect.Rect(shop_rect.topright[0]-W/38.4, shop_rect.topright[1]-H/21.6, W/19.2, H/10.8)
shop_button_copies = [(i["color"], pygame.Rect(SW/12, (SH/8)*(idx+1), i.get("size", 50)*2, i.get("size", 50)*2), v, idx, font1.render(v, False, "#ffffff"), font2.render(str(i["cost"]), False, "#ffffff")) for idx, (v, i) in enumerate(towerTemp.items())]
towerupgradespos = ((W/5)*3.9, (H/12))
towerupgradesurf = pygame.Surface((W/5, (H/6)*5))
UW, UH = towerupgradesurf.get_width(), towerupgradesurf.get_height()
towerupgradebutton = pygame.Rect(UW/8, (UH/5)*4, (UW/4)*3, (UH/8))
towersellbutton = pygame.Rect(UW/8, (UH/5)*4.65, (UW/4)*3, (UH/16))

def events(dt):
    global running, gui, phtower, placing_tower, shopy, shopmaxy, mx, my, selected
    mpos = pygame.mouse.get_pos()
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False
            break
        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                running = False
                break
            elif e.key == pygame.K_m:
                if gui != 2: 
                    if gui == 1:
                        gui = 0
                    else:
                        gui = 1
            elif e.key == pygame.K_q:
                if gui == 2:
                    placing_tower = False
                    phtower = 0
                    gui = 0
# --- MOBILE TOUCH SUPPORT ---
        elif hasattr(pygame, "FINGERDOWN") and e.type == pygame.FINGERDOWN:
            # Convert mobile 0.0-1.0 to pixel coordinates
            tx, ty = e.x * W, e.y * H
            curr_time = pygame.time.get_ticks() / 1000.0
            
            if gui == 1: # Start scroll tracking
                game.touch_start_y = ty
                # Check for shop selection
                relative_mpos = (tx - shop_rect.x, ty - shop_rect.y)
                for tower_button in shop_button_copies:
                    if tower_button[1].collidepoint(relative_mpos):
                        phtower = placeholderTower(tower_button[2])
                        if game.money >= phtower.cost:
                            gui = 2
                            placing_tower = True
            
            elif gui == 2: # Mobile Placement Logic
                # Only attempt placement if it's a double tap
                if curr_time - game.last_tap_time < 0.3:
                    if not tower_cancel_rect.collidepoint((tx, ty)):
                        if len(towers) < game.tower_limit:
                            # 1. Check Tower-to-Tower Collision
                            can_place = True
                            for t in towers:
                                if math.hypot(tx - t.x, ty - t.y) < 80:
                                    can_place = False
                                    break
                            
                            # 2. Check Road Collision
                            on_road = False
                            for i in range(len(game.map) - 1):
                                p1, p2 = game.map[i], game.map[i+1]
                                dx, dy = p2[0]-p1[0], p2[1]-p1[1]
                                if dx == 0 and dy == 0: continue
                                t_val = ((tx-p1[0])*dx + (ty-p1[1])*dy) / (dx*dx + dy*dy)
                                t_val = max(0, min(1, t_val))
                                nearest_x, nearest_y = p1[0]+t_val*dx, p1[1]+t_val*dy
                                if math.hypot(tx-nearest_x, ty-nearest_y) < 45:
                                    on_road = True
                                    break

                            if can_place and not on_road and game.money >= phtower.cost:
                                towers.append(Tower(tx, ty, phtower.name))
                                game.dec_money(phtower.cost)
                                # Only exit placement mode if placement was successful or canceled
                                phtower = 0
                                placing_tower = False
                                gui = 0
                    else:
                        # If they hit the cancel button
                        phtower = 0
                        placing_tower = False
                        gui = 0
                
                # Update the last tap time EVERY time they tap in GUI 2
                game.last_tap_time = curr_time

        elif hasattr(pygame, "FINGERMOTION") and e.type == pygame.FINGERMOTION:
            if gui == 1: # Swipe to Scroll
                shopy -= e.dy * H 
                shopy = max(0, min(shopy, shopmaxy))

        # --- ORIGINAL PC MOUSE LOGIC (Untouched) ---
        elif e.type == pygame.MOUSEBUTTONDOWN:
            if e.button == 1:
                if skip_wave_rect.collidepoint(e.pos):
                    if len(enemies) == 0:
                        game.skip_wave()
                elif gui == 0:
                    if shop_button_rect.collidepoint(e.pos):
                        gui = 1
                    else:
                        for i, t in enumerate(towers):
                            if t.rect.collidepoint(e.pos):
                                gui = 3
                                selected = t
                                break
                elif gui == 1:
                    if shop_close_button_rect.collidepoint(e.pos):
                        placing_tower = False
                        phtower = 0
                        gui = 0
                    else:
                        relative_mpos = (e.pos[0] - shop_rect.x, e.pos[1] - shop_rect.y)
                        for tower_button in shop_button_copies:
                            if tower_button[1].collidepoint(relative_mpos):
                                phtower = placeholderTower(tower_button[2])
                                if game.money >= phtower.cost:
                                    gui = 2
                                    placing_tower = True
                                else:
                                    phtower = 0
                                    gui = 1
                elif gui == 2:
                    if phtower != 0:
                        # Check if limit is reached
                        if len(towers) < game.tower_limit:
                            # Create a variable to see if the spot is valid
                            can_place = True
                            for t in towers:
                                # Calculate distance between cursor (mpos) and existing tower
                                dist = math.hypot(e.pos[0] - t.x, e.pos[1] - t.y)
                                if dist < 80: # 60 pixels is the "Red Circle" zone
                                    can_place = False
                                    break

                            if can_place and len(towers) < game.tower_limit:
                                towers.append(Tower(e.pos[0], e.pos[1], phtower.name))
                                game.dec_money(phtower.cost)
                            phtower = 0
                            placing_tower = False
                            gui = 0
                        else:
                            # Optional: Add a visual warning or sound here
                            print("Tower Limit Reached!")
                elif gui == 3:
                    tuboffset = towerupgradebutton.move(towerupgradespos)
                    tusoffset = towersellbutton.move(towerupgradespos)
                    surf = towerupgradesurf.get_rect(topleft=towerupgradespos)
                    if surf.collidepoint(e.pos):
                        if tuboffset.collidepoint(e.pos):
                            if selected.lvl != selected.maxlvl:
                                selected.upgrade()
                        elif tusoffset.collidepoint(e.pos):
                            selected.sell()
                            gui = 0
                    elif game.targeting_button_rect.move(towerupgradespos).collidepoint(e.pos):
                    # Toggle between modes
                        selected.mode = "strongest" if selected.mode == "first" else "first"
                    else:
                        for i, t in enumerate(towers):
                            if t.rect.collidepoint(e.pos):
                                gui = 3
                                selected = t
                                return
                        gui = 0
                if game.speed_button_rect.collidepoint(e.pos):
                    # Cycle through 1x -> 2x -> 3x -> 1x
                    game.speed_multiplier = game.speed_multiplier + 1 if game.speed_multiplier < 10 else 1
        elif e.type == pygame.MOUSEWHEEL:
            if e.y > 0:
                shopy -= 35
            elif e.y < 0:
                shopy += 35
            if shopy < 0:
                shopy = 0
            elif shopy > shopmaxy:
                shopy = shopmaxy
        elif e.type == pygame.MOUSEMOTION:
            mx, my = e.pos
            for enemy in enemies:
                if enemy:
                    if enemy.rect.collidepoint((mx, my)):
                        game.cached_draw(w, font1, f"{enemy.hp} / {enemy.maxhp}", "#ffffff", (mx, my), False)

def draw(dt):
    global selected
    w.fill("#000000")
    pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
    pygame.draw.lines(w, "#494949", False, game.map, 5)
    for enemy in enemies:
        enemy.step(dt)
    for tower in towers:
        tower.update(dt, enemies)
        pygame.draw.rect(w, tower.col, tower.rect)
    for idx, obj in enumerate(temporary):
            if obj[1] < 0:
                temporary.pop(idx)
                continue
            temporary[idx][1] -= dt
            pygame.draw.circle(w, obj[0][0], obj[0][1], obj[0][2], 1)
    for obj in projectiles:
        pygame.draw.rect(w, obj.col, obj.rect)
        obj.update(dt)
    if len(enemies) == 0 and game.candrawskip:
        pygame.draw.rect(w, "#00ff00", skip_wave_rect)
        game.cached_draw(w, font3, "Instant-Skip", "#000000", skip_wave_rect.center, True)
    if selected is not None:
        pygame.draw.circle(w, (255, 255, 255), selected.rect.center, selected.range, 10)
    if gui == 0:
        if shop_button_rect.collidepoint((mx,my)):
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
        pygame.draw.rect(w, "#ff0000", shop_button_rect)
        selected = None
        for e in enemies:
            if e.rect.collidepoint((mx, my)):
                game.cached_draw(w, font1, e.name, "#ffffff", (mx, my-H/30), True)
                game.cached_draw(w, font2, f"{e.hp} / {e.maxhp}", "#ffffff", (mx, my), True)
                break
        for t in towers[::-1]:
            if t.rect.collidepoint((mx, my)):
                if t.lvl != t.maxlvl:
                    game.cached_draw(w, font2, f"Level: {t.lvl} / {t.maxlvl}", "#ffffff", (mx, my), True)
                else:
                    game.cached_draw(w, font2, "MAX LEVEL", "#ffffff", (mx, my), True)
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
                game.cached_draw(w, font1, f"{t.name}", "#ffffff", (mx, my-H/30), True)
                pygame.draw.circle(w, (255, 255, 255), t.rect.center, t.range, 10)
                if t.aoeangle > 0:
                    r = t.range
                    cap = r * 2
                    # Yayın tam düşmana bakması için: merkez_açı - (toplam_açı / 2)
                    start_angle = t.angle - (t.aoeangle / 2)
                    end_angle = t.angle + (t.aoeangle / 2)
                    
                    alan = (t.rect.centerx - r, t.rect.centery - r, cap, cap)
                    
                    # Yayı çiz
                    pygame.draw.arc(w, "#ffff00", alan, math.radians(start_angle), math.radians(end_angle), 5)
                    
                    # 1. Çizgi: Başlangıç açısı kolu
                    p1 = (t.rect.centerx + r * math.cos(math.radians(start_angle)), 
                        t.rect.centery - r * math.sin(math.radians(start_angle)))
                    pygame.draw.line(w, "#ffff00", t.rect.center, p1, 5)
                    
                    # 2. Çizgi: Bitiş açısı kolu
                    p2 = (t.rect.centerx + r * math.cos(math.radians(end_angle)), 
                        t.rect.centery - r * math.sin(math.radians(end_angle)))
                    pygame.draw.line(w, "#ffff00", t.rect.center, p2, 5)
                break
    elif gui == 1:
        shop_surf.fill("#707070")
        for button in shop_button_copies:
            button[1].y = (SH/5)*(button[3]+1)-shopy
            pygame.draw.rect(shop_surf, button[0], button[1])
            shop_surf.blit(button[4], (button[1].centerx + SH/12, button[1].centery - 30))
            shop_surf.blit(button[5], (button[1].centerx + SH/12, button[1].centery + 10))
            relative_mpos = (mx - shop_rect.x, my - shop_rect.y)
            if button[1].collidepoint(relative_mpos):
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
        if shop_close_button_rect.collidepoint((mx, my)):
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND) 
        w.blit(shop_surf, (W/2-((W/3)*2)/2, H/2-(H/4*3)/2))
        pygame.draw.circle(w, "#ff0000", (shop_rect.topright[0], shop_rect.topright[1]), int(W/38.4))
    elif gui == 2:
        if phtower != 0:
            phtower.update()
            pygame.draw.rect(w, phtower.col, phtower.rect)
            pygame.draw.rect(w, "#ff0000", tower_cancel_rect)
            pygame.draw.circle(w, (255, 255, 255), phtower.rect.center, phtower.range, 10)
# Draw Red Collision Circles around existing towers
            for t in towers:
                pygame.draw.circle(w, "#ff0000", t.rect.center, 80, 2) # 2 is the thickness
            
            phtower.update()
            
            # Change placeholder color to red if overlapping
            mpos = pygame.mouse.get_pos()
            overlap = any(math.hypot(mpos[0]-t.x, mpos[1]-t.y) < 80 for t in towers)
            
            # Draw the placement range circle
            draw_col = "#ff0000" if overlap else (255, 255, 255)
            pygame.draw.circle(w, draw_col, phtower.rect.center, phtower.range, 5)
            
            pygame.draw.rect(w, phtower.col, phtower.rect)
            pygame.draw.rect(w, "#ff0000", tower_cancel_rect)
    elif gui == 3:
        tuboffset = towerupgradebutton.move(towerupgradespos)
        tusoffset = towersellbutton.move(towerupgradespos)
        if tuboffset.collidepoint((mx, my)):
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND) 
        elif tusoffset.collidepoint((mx, my)):
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND) 
        towerupgradesurf.fill("#4a4a4a")
        game.cached_draw(towerupgradesurf, font1, selected.name, "#000000", (UW/2, UH/5), True)
        # Targeting Toggle Button
        pygame.draw.rect(towerupgradesurf, "#5555ff", game.targeting_button_rect)
        game.cached_draw(towerupgradesurf, font2, f"Target: {selected.mode.upper()}", "#ffffff", game.targeting_button_rect.center, True)
        if selected.lvl != selected.maxlvl:
            game.cached_draw(towerupgradesurf, font2, selected.upgs[selected.lvl]["name"], "#000000", (UW/2, (UH/5)*1.5), True)
            game.cached_draw(towerupgradesurf, font2, selected.upgs[selected.lvl]["desc"], "#000000", (UW/2, (UH/5)*2), True)
            pygame.draw.rect(towerupgradesurf, "#00aa00", towerupgradebutton)
            game.cached_draw(towerupgradesurf, font1, selected.nextupgradeprice, "#000000", towerupgradebutton.center, True)
        game.cached_draw(towerupgradesurf, font2, f"total damage: {selected.totaldmg}", "#000000", (UW/2, (UH/5)*2.5), True)
        pygame.draw.rect(towerupgradesurf, "#aa0000", towersellbutton)
        game.cached_draw(towerupgradesurf, font2, selected.sellprice, "#000000", towersellbutton, True)
        w.blit(towerupgradesurf, towerupgradespos)
        for e in enemies:
            if e.rect.collidepoint((mx, my)):
                game.cached_draw(w, font1, e.name, "#ffffff", (mx, my-H/30), True)
                game.cached_draw(w, font2, f"{e.hp} / {e.maxhp}", "#ffffff", (mx, my), True)
                break
        for t in towers:
            if t.rect.collidepoint((mx, my)):
                if t.lvl != t.maxlvl:
                    game.cached_draw(w, font2, f"Level: {t.lvl} / {t.maxlvl}", "#ffffff", (mx, my), True)
                else:
                    game.cached_draw(w, font2, "MAX LEVEL", "#ffffff", (mx, my), True)
                game.cached_draw(w, font1, f"{t.name}", "#ffffff", (mx, my-H/30), True)
        if selected.aoeangle > 0:
            r = selected.range
            cap = r * 2
            # Yayın tam düşmana bakması için: merkez_açı - (toplam_açı / 2)
            start_angle = selected.angle - (selected.aoeangle / 2)
            end_angle = selected.angle + (selected.aoeangle / 2)
            
            alan = (selected.rect.centerx - r, selected.rect.centery - r, cap, cap)
            
            # Yayı çiz
            pygame.draw.arc(w, "#ffff00", alan, math.radians(start_angle), math.radians(end_angle), 5)
            
            # 1. Çizgi: Başlangıç açısı kolu
            p1 = (selected.rect.centerx + r * math.cos(math.radians(start_angle)), 
                selected.rect.centery - r * math.sin(math.radians(start_angle)))
            pygame.draw.line(w, "#ffff00", selected.rect.center, p1, 5)
            
            # 2. Çizgi: Bitiş açısı kolu
            p2 = (selected.rect.centerx + r * math.cos(math.radians(end_angle)), 
                selected.rect.centery - r * math.sin(math.radians(end_angle)))
            pygame.draw.line(w, "#ffff00", selected.rect.center, p2, 5)
    elif gui == 4: # VICTORY SCREEN
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        s.fill((0, 150, 0, 180)) # Semi-transparent green
        w.blit(s, (0,0))
        game.cached_draw(w, font1, "VICTORY!", "#ffffff", (W/2, H/2 - 50), True)
        game.cached_draw(w, font2, f"The Singularity has been contained. Final Funds: {game.money}$", "#ffffff", (W/2, H/2 + 20), True)
        game.cached_draw(w, font3, "Press ESC to Quit", "#ffffff", (W/2, H/2 + 80), True)

    elif gui == 5: # FAIL SCREEN
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        s.fill((150, 0, 0, 180)) # Semi-transparent red
        w.blit(s, (0,0))
        game.cached_draw(w, font1, "BASE DESTROYED", "#ffffff", (W/2, H/2 - 50), True)
        game.cached_draw(w, font2, f"You reached Wave {game.wave}", "#ffffff", (W/2, H/2 + 20), True)
        game.cached_draw(w, font3, "Press ESC to Quit", "#ffffff", (W/2, H/2 + 80), True)
# --- BOSS HP BAR ADJUSTMENT ---
    for e in enemies:
        if e.name == "The Singularity":
            bar_width = W // 2
            bar_height = 40
            bar_x = (W - bar_width) // 2
            bar_y = 80
            # Background
            pygame.draw.rect(w, (50, 50, 50), (bar_x, bar_y, bar_width, bar_height))
            # Health fill
            fill = (e.hp / e.maxhp) * bar_width
            pygame.draw.rect(w, (200, 0, 0), (bar_x, bar_y, fill, bar_height))
            # Text
            game.cached_draw(w, font2, f"FINAL BOSS: {int(e.hp)} / {e.maxhp}", "#ffffff", (W//2, bar_y + 20), True)
# Speed Button
    pygame.draw.rect(w, "#333333", game.speed_button_rect)
    game.cached_draw(w, font2, f"{game.speed_multiplier}x Speed", "#ffffff", game.speed_button_rect.center, True)
    game.cached_draw(w, font1, f"{game.money}$", "#00ff00", (W/2, 50), True)
    game.cached_draw(w, font1, f"Wave: {game.wave}", "#00ff00", (W- W/6, 50), True)
    game.cached_draw(w, font1, f"Health: {base.hp} / {base.maxhp}", "#00ff00", (W/6, 50), True)
    # Tower Limit Counter
    limit_color = "#00ff00" if len(towers) < game.tower_limit else "#ff0000"
    game.cached_draw(w, font2, f"Towers: {len(towers)} / {game.tower_limit}", limit_color, (W/6, 90), True)
    pygame.display.flip()

async def main():
    global running 
    import platform
    if platform.system() == "Emscripten":
        import js
        js.window.eval("window.is_background_active = true;")
    while running:
        dt = (clock.tick(maxfps) / 1000.0) * game.speed_multiplier
        dt = min(dt, 0.2)
        game.next_ev(dt)
        events(dt)
        draw(dt)
        await asyncio.sleep(0)

asyncio.run(main())
pygame.quit()