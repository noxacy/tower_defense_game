import pygame
import json
import os
import asyncio

pygame.init()
Info = pygame.display.Info()
W, H = Info.current_w, Info.current_h
w = pygame.display.set_mode((W, H), pygame.FULLSCREEN)
running = True
clock = pygame.time.Clock()
maxfps = 60
gui = 0
font1 = pygame.font.SysFont(None, 50)
font2 = pygame.font.SysFont(None, 35)
font3 = pygame.font.SysFont(None, 20)
mx, my = 0, 0
cache = {}
with open("templates.json", "r") as f:
    full = json.load(f)
    towerTemp = full["towers"]
    enemyTemp = full["enemies"]
    route = full["route"]

class Base:
    def __init__(self):
        self.maxhp = 250
        self.hp = self.maxhp

    def decrease_hp(self, amount):
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            game.game_over()

    def increase_hp(self, amount):
        self.hp += amount
        if self.hp > 250:
            self.hp = 250

class Game:
    def __init__(self):
        global gui, route
        self.map = [(W/4, H), (W/4, H/5), (W/4*3, H/5), (W/4*3, H/5*4), (W/2, H/5*4), (W/2, H/5*2), (W, H/5*2)]
        self.money = 5500000
        self.text_cache = {}
        self.waittime = 0
        self.quant = 0
        self.wave = 1
        self.ev = -1
        self.end = False
        self.skip = False
        self.candrawskip = False

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
            return
        ev = self.get_ev()
        wave = route[f"wave{self.wave}"]
        cWave = wave[self.ev]
        if self.waittime <= 0:
            if self.ev == -1:
                if self.wave != 1:
                    self.inc_money(route[f"wave{self.wave - 1}"][-1][1])
                self.wave += 1
                if self.wave > len(route):
                    self.end = True
            if ev == "spawn":
                self.candrawskip = False
                if self.quant == 0:
                    self.ev += 1
                    if self.ev < len(wave)-1:
                        cWave = wave[self.ev]
                        self.quant = cWave["quantity"]
                else:
                    enemies.append(Enemy(cWave["name"]))
                    self.waittime = cWave["cooldown"]
                    self.quant -= 1
            elif ev == "end":
                self.waittime = cWave[0] - wave[self.ev - 1]["cooldown"]
                self.candrawskip = True
                self.ev = -1
                self.quant = 0
        else:
            self.waittime -= dt

    def skip_wave(self):
        if self.candrawskip:
            self.waittime = 0

    def game_over(self):
        global gui
        gui = 3

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
        else:
            raise ValueError(f"\"{enemy}\" enemy is not in enemy templates.")

    def step(self, dt):
        if self.nt:
            self.idx += 1
            self.nt = False
        if self.idx + 1 > len(game.map):
            enemies.remove(self)
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
            self.lvl = 0
            self.nextupgradeprice = self.upgs[self.lvl]["price"]
            self.totaldmg = 0
            self.cost = full["cost"]
            self.sellprice = self.cost
            self.maxlvl = len(self.upgs)
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
        self.sellprice += int(self.nextupgradeprice/1.5)
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
        if self.waittime <= 0:
            elist = self.get_in_range(enemies)
            if len(elist) > 0:
                if self.mode == "first":
                    theone_data = max(elist, key=lambda x: x[0].process)
                    target_enemy = theone_data[0]
                elif self.mode == "strongest":
                    theone_data = max(elist, key=lambda x: x[0].maxhp)
                    target_enemy = theone_data[0]
                target_enemy.take_damage(self.dmg)
                self.totaldmg += self.dmg
                self.waittime = self.frate

    def sell(self):
        game.inc_money(self.sellprice)
        towers.remove(self)

towers = []
enemies = []
shop_button_rect = pygame.Rect(W/128, H-H/9, W/5.5, H/10)
skip_wave_rect = pygame.Rect(0,0,W/19.2,H/10.8)
skip_wave_rect.center=(W/128*125.2-W/19.2,H/72*65-H/10.8) 
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
            elif e.key == pygame.K_1:
                enemies.append(Enemy("Normal"))
            elif e.key == pygame.K_2:
                enemies.append(Enemy("Swift"))
            elif e.key == pygame.K_3:
                enemies.append(Enemy("Heavy"))
            elif e.key == pygame.K_4:
                enemies.append(Enemy("Leader"))
            elif e.key == pygame.K_5:
                enemies.append(Enemy("Shadow"))
            elif e.key == pygame.K_6:
                enemies.append(Enemy("Witch"))
            elif e.key == pygame.K_7:
                enemies.append(Enemy("Myth"))
            elif e.key == pygame.K_8:
                enemies.append(Enemy("Healthy"))
            elif e.key == pygame.K_9:
                enemies.append(Enemy("Lightspeed"))
            elif e.key == pygame.K_q:
                if gui == 2:
                    placing_tower = False
                    phtower = 0
                    gui = 0
        elif e.type == pygame.MOUSEBUTTONDOWN:
            if e.button == 1:
                if gui == 0:
                    if shop_button_rect.collidepoint(e.pos):
                        gui = 1
                    elif skip_wave_rect.collidepoint(e.pos):
                        if len(enemies) == 0:
                            game.skip_wave()
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
                        if not tower_cancel_rect.collidepoint(e.pos):
                            towers.append(Tower(mpos[0], mpos[1], phtower.name))
                            game.dec_money(phtower.cost)
                        phtower = 0
                        placing_tower = False
                        gui = 0
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
                    else:
                        gui = 0
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
    w.fill("#000000")
    pygame.draw.lines(w, "#494949", False, game.map, 5)
    for enemy in enemies:
        enemy.step(dt)
    for tower in towers:
        tower.update(dt, enemies)
        pygame.draw.rect(w, tower.col, tower.rect)
        pygame.draw.circle(w, (255, 255, 255), tower.rect.center, tower.range, 10)
    if gui == 0:
        pygame.draw.rect(w, "#ff0000", shop_button_rect)
        if len(enemies) == 0 and game.candrawskip:
            pygame.draw.rect(w, "#00ff00", skip_wave_rect)
            game.cached_draw(w, font3, "Instant-Skip", "#000000", skip_wave_rect.center, True)
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
    elif gui == 1:
        shop_surf.fill("#707070")
        for button in shop_button_copies:
            button[1].y = (SH/5)*(button[3]+1)-shopy
            pygame.draw.rect(shop_surf, button[0], button[1])
            shop_surf.blit(button[4], (button[1].centerx + SH/12, button[1].centery - 30))
            shop_surf.blit(button[5], (button[1].centerx + SH/12, button[1].centery + 10))
        w.blit(shop_surf, (W/2-((W/3)*2)/2, H/2-(H/4*3)/2))
        pygame.draw.circle(w, "#ff0000", (shop_rect.topright[0], shop_rect.topright[1]), int(W/38.4))
    elif gui == 2:
        if phtower != 0:
            phtower.update()
            pygame.draw.rect(w, phtower.col, phtower.rect)
            pygame.draw.rect(w, "#ff0000", tower_cancel_rect)
    elif gui == 3:
        towerupgradesurf.fill("#4a4a4a")
        game.cached_draw(towerupgradesurf, font1, selected.name, "#000000", (UW/2, UH/5), True)
        if selected.lvl != selected.maxlvl:
            game.cached_draw(towerupgradesurf, font2, selected.upgs[selected.lvl]["name"], "#000000", (UW/2, (UH/5)*1.5), True)
            game.cached_draw(towerupgradesurf, font3, selected.upgs[selected.lvl]["desc"], "#000000", (UW/2, (UH/5)*2), True)
            pygame.draw.rect(towerupgradesurf, "#00aa00", towerupgradebutton)
            game.cached_draw(towerupgradesurf, font1, selected.nextupgradeprice, "#000000", towerupgradebutton.center, True)
        game.cached_draw(towerupgradesurf, font3, f"total damage: {selected.totaldmg}", "#000000", (UW/2, (UH/5)*2.5), True)
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
    game.cached_draw(w, font1, f"{game.money}$", "#00ff00", (W/2, 50), True)
    game.cached_draw(w, font1, f"Wave {game.wave - 1}", "#00ff00", (W/4*3, 50), True)
    game.cached_draw(w, font1, f"{base.hp} / {base.maxhp}", "#00ff00", (W/4, 50), True)
    pygame.display.flip()

async def main():
    global running 
    while running:
        dt = clock.tick(maxfps) / 1000.0
        game.next_ev(dt)
        events(dt)
        draw(dt)
        await asyncio.sleep(0)

asyncio.run(main())
pygame.quit()

#a