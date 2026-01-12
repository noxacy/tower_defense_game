import pygame, sys, time, random, asyncio, json

pygame.init()
pygame.display.set_caption("Akif Clicker v1.0")
WIDTH, HEIGHT = 1920, 1080
screen = pygame.display.set_mode((WIDTH,HEIGHT))
clock = pygame.time.Clock()

akif = pygame.image.load("./assets/akifclicker.png").convert_alpha()
bg = pygame.image.load("./assets/abc.jpg").convert()
boximg = pygame.image.load("./assets/Box.png").convert_alpha()
smallboximg = pygame.image.load("./assets/SmallBox.png").convert_alpha()
font = pygame.font.Font("./assets/ByteBounce.ttf", 50)
font_med = pygame.font.Font("./assets/ByteBounce.ttf", 35)
font_small = pygame.font.Font("./assets/ByteBounce.ttf", 25)
clicksound = pygame.mixer.Sound("./assets/lmb.ogg")

class Particle:
    def __init__(self, x, y, text):
        self.x, self.y, self.alpha, self.vy = x, y, 255, -2
        self.text = font_small.render(text, True, "white")
    def update(self): self.y += self.vy; self.alpha -= 5
    def draw(self, surf):
        self.text.set_alpha(self.alpha); surf.blit(self.text, (self.x, self.y))

class Game():
    def __init__(self):
        self.m, self.mps, self.mpc, self.click = 0, 0, 1, 0
        self.akif_rect = pygame.Rect(15, 45, 250, 250)
        self.mode_btn_rect = pygame.Rect(15, 310, 250, 50) # Yeni Yerleşim
        self.particles, self.akif_scale = [], 1.0
        self.golden_akif_timer, self.golden_akif_active = random.randint(120, 180), False
        self.golden_akif_rect = pygame.Rect(0, 0, 100, 100)
        self.buy_modes, self.buy_mode_index = [1, 10, 100], 0
        self.current_buy_amount = 1
        self.click_to_mps_ratio = 0  # Başlangıçta 0, upgrade ile 0.05 olacak
        self.raw_mpc = 1


        self.buildings = [
            ["Kenan", "Clicks the news.", 20, 1, 1, 1190, 15, 0, 1.15],
            ["Deniz", "Buys grandmas.", 150, 6, 1, 1555, 15, 0, 1.16],
            ["Zeki", "Plays tennis.", 1500, 18, 1, 1190, 130, 0, 1.17],
            ["Agah", "SHUT UP!", 18000, 75, 1, 1555, 130, 0, 1.18],
            ["Poyraz", "PDF Reader", 220000, 450, 1, 1190, 245, 0, 1.19],
            ["Huzeyfe", "AkifCoin Miner", 2.8*10**6, 2200, 1, 1555, 245, 0, 1.20],
            ["Dimes", "Worships juice.", 4.5*10**7, 12000, 1, 1190, 360, 0, 1.21],
            ["Seyfullah", "Is Annoying", 8*10**8, 70000, 1, 1555, 360, 0, 1.22],
            ["Suheyla", "Draws M. Kemal", 1.5*10**10, 400000, 1, 1190, 475, 0, 1.23],
            ["Black Deniz", "Dark Grandmas.", 2.5*10**11, 2.5*10**6, 1, 1555, 475, 0, 1.24],
            ["AYTGames", "Pro Gamer.", 5*10**12, 1.8*10**7, 1, 1190, 590, 0, 1.25],
            ["Can K.", "Math Genius.", 9*10**13, 1.2*10**8, 1, 1555, 590, 0, 1.26],
            ["EGE", "Plays CR.", 1.8*10**15, 9*10**8, 1, 1190, 705, 0, 1.27],
            ["Ruzgar", "Talks in class.", 3.5*10**16, 7.5*10**9, 1, 1555, 705, 0, 1.28],
            ["Sukru", "Alhamdulillah.", 7*10**17, 6*10**10, 1, 1190, 820, 0, 1.29],
            ["Yigit", "Just exists.", 1.5*10**19, 5*10**11, 1, 1555, 820, 0, 1.30],
            ["Theomen", ":)", 4*10**20, 4.5*10**12, 1, 1190, 935, 0, 1.35],
            ["Child Man", "-dam", 5*10**25, 5*10**13, 1, 1555, 935, 0, 1.0]
        ]
        self.b_scales = [1.0] * len(self.buildings)
        self.upgrades = []
        for i, b in enumerate(self.buildings):
            if i == 17: continue 
            self.upgrades.append([f"{b[0]} T1", f"{b[0]} 2x eff.", int(b[2]*15), False, i, 10])
            self.upgrades.append([f"{b[0]} T2", f"{b[0]} 2x eff.", int(b[2]*100), False, i, 25])
            if i % 4 == 0: self.upgrades.append(["Global Coach", "+5% Total MPS.", int(b[2]*50), False, -1, 1])

        self.upgrades.append(["Finger Strength I", "Raw Click 2x", 100, False, -3, 10])   # 10 clickte açılır
        self.upgrades.append(["Finger Strength II", "Raw Click 2x", 1000, False, -4, 100]) # 100 clickte açılır
        self.upgrades.append(["Finger Strength III", "Raw Click 2x", 10000, False, -5, 250])# 250 clickte açılır
        self.upgrades.append([
            "Auto-Clicker Synergy", 
            "Click = 5% of MPS", 
            500000, # Fiyatı (istediğin gibi ayarla)
            False, 
            -2,     # Özel bir ID veriyoruz (örneğin -2)
            1000   # Açılması için gereken tıklama sayısı
        ])
            

    def get_bulk_price(self, bid, amt):
        b = self.buildings[bid]
        return b[2] * ((b[8]**amt) - 1) / (b[8] - 1)

    def update_total_mps(self):
        t = sum(b[3] * b[4] * b[7] for b in self.buildings)
        for u in self.upgrades:
            if u[4] == -1 and u[3]: t *= 1.05
        cmc = self.buildings[17][7]
        if cmc > 0: t *= (1.05 ** cmc)
        self.mps = t
        if self.click_to_mps_ratio > 0:
            self.mpc = max(1, int(self.mps * self.click_to_mps_ratio))
        else:
            self.mpc = 1 # Başlangıç değeri

        self.mpc = self.raw_mpc + int(self.mps * self.click_to_mps_ratio)   

    def building(self, bid, x, y):
        rect = pygame.Rect(x, y, 350, 100)
        img = boximg.copy()
        if rect.collidepoint(pygame.mouse.get_pos()): img.fill((40, 40, 40), special_flags=pygame.BLEND_RGB_ADD)
        s_img = pygame.transform.smoothscale(img, (int(350*self.b_scales[bid]), int(100*self.b_scales[bid])))
        s_rect = s_img.get_rect(center=rect.center)
        screen.blit(s_img, s_rect)

        price = (5*10**25 + self.mps*1000) if bid == 17 else self.get_bulk_price(bid, self.current_buy_amount)
        p_color = "#15ff00" if self.m >= price else "#ff1500"
        
        screen.blit(font_med.render(self.buildings[bid][0], True, "white"), (s_rect.x+15, s_rect.y+10))
        screen.blit(font_small.render(compress(price), True, p_color), (s_rect.right-100, s_rect.y+15))
        screen.blit(font_med.render(f"x{self.buildings[bid][7]}", True, "#555555"), (s_rect.right-60, s_rect.y+45))
        screen.blit(font_small.render(self.buildings[bid][1], True, "#929292"), (s_rect.x+15, s_rect.y+65))
        screen.blit(font_small.render(f"{compress(self.buildings[bid][3]*self.buildings[bid][4])} mps", True, "#c0c0c0"), (s_rect.right-100, s_rect.bottom-25))

    def handle_clicks(self, pos):
        if self.akif_rect.collidepoint(pos):
            self.m += self.mpc; self.click += 1; self.akif_scale = 0.8; clicksound.play()
            self.particles.append(Particle(pos[0], pos[1], f"+{compress(self.mpc)}"))
        
        # Mod Butonu Tıklama (Yeni Yer)
        if self.mode_btn_rect.collidepoint(pos):
            self.buy_mode_index = (self.buy_mode_index + 1) % 3
            self.current_buy_amount = self.buy_modes[self.buy_mode_index]
            clicksound.play()

        for i, b in enumerate(self.buildings):
            if pygame.Rect(b[5], b[6], 350, 100).collidepoint(pos):
                amt = 1 if i == 17 else self.current_buy_amount
                cost = (5*10**25 + self.mps*1000) if i == 17 else self.get_bulk_price(i, amt)
                if self.m >= cost:
                    self.m -= cost; self.buildings[i][7] += amt
                    if i != 17: self.buildings[i][2] *= (self.buildings[i][8]**amt)
                    self.update_total_mps(); self.b_scales[i] = 0.92; clicksound.play()

        ux, uy, count = 15, 750, 0
        for i, u in enumerate(self.upgrades):
            # Görünürlük Şartı: Tıklama bazlı olanları kontrol et
            is_visible = (u[4] == -1 and self.m > u[2]*0.3) or \
                         (u[4] in [-2, -3, -4, -5] and self.click >= u[5]) or \
                         (u[4] >= 0 and self.buildings[u[4]][7] >= u[5])
            
            if not u[3] and is_visible:
                u_rect = pygame.Rect(ux + (count%3)*115, uy + (count//3)*115, 100, 100)
                if u_rect.collidepoint(pos) and self.m >= u[2]:
                    self.m -= u[2]
                    u[3] = True
                    
                    if u[4] == -2: # Synergy
                        self.click_to_mps_ratio = 0.05
                    elif u[4] in [-3, -4, -5]: # Raw Click Katlayıcılar
                        self.raw_mpc *= 2
                    elif u[4] != -1: # Bina Upgradeleri
                        self.buildings[u[4]][4] *= 2
                    
                    self.update_total_mps() # MPC'yi (Raw + %5 MPS) yeniden hesaplar
                    clicksound.play()
                
                count += 1
                if count >= 9: break

            # Golden Akif Tıklama Kontrolü
        if self.golden_akif_active and self.golden_akif_rect.collidepoint(pos):
            self.m += max(500, int(self.mps * 600))
            self.golden_akif_active = False
            # KRİTİK: Tıklandığı an yeni bir rastgele süre belirle
            self.golden_akif_timer = random.randint(120, 180) 
            clicksound.play()

def compress(n):
    u = ["", "K", "M", "B", "T", "Qa", "Qi", "Sx", "Sp", "Oc", "No", "Dc"]
    i = 0
    while n >= 1000 and i < len(u)-1: n /= 1000; i += 1
    return f"{round(n, 1)}{u[i]}"

game = Game()

async def main():
    last_save = time.time()
    while True:
        dt = clock.tick(60) / 1000
        m_pos = pygame.mouse.get_pos()
        is_h = False
        
        for e in pygame.event.get():
            if e.type == pygame.QUIT: pygame.quit(); sys.exit()
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1: game.handle_clicks(e.pos)
            if e.type == pygame.KEYDOWN and e.key == pygame.K_TAB:
                game.buy_mode_index = (game.buy_mode_index + 1) % 3
                game.current_buy_amount = game.buy_modes[game.buy_mode_index]

        game.m += game.mps * dt
        game.akif_scale += (1.0 - game.akif_scale) * 0.1
        for i in range(len(game.b_scales)): game.b_scales[i] += (1.0 - game.b_scales[i]) * 0.1
        for p in game.particles[:]:
            p.update()
            if p.alpha <= 0: game.particles.remove(p)

        if not game.golden_akif_active:
            game.golden_akif_timer -= dt
            if game.golden_akif_timer <= 0: 
                game.golden_akif_pos = [random.randint(300, 1400), random.randint(100, 700)]
                game.golden_akif_rect.topleft = game.golden_akif_pos
                game.golden_akif_active, game.golden_akif_life = True, 10.0
        else:
            game.golden_akif_life -= dt
            if game.golden_akif_life <= 0: game.golden_akif_active = False; game.golden_akif_timer = random.randint(60, 120)

        screen.blit(bg, (0,0))
        screen.blit(font.render(f"{compress(game.m)} Money", True, "white"), (280, 50))
        screen.blit(font_med.render(f"{compress(game.mps)} per second", True, "#c0c0c0"), (280, 100))
        
        s_akif = pygame.transform.smoothscale(akif, (int(250*game.akif_scale), int(250*game.akif_scale)))
        a_r = s_akif.get_rect(center=game.akif_rect.center)
        if a_r.collidepoint(m_pos): is_h = True
        screen.blit(s_akif, a_r)
        
        for i, b in enumerate(game.buildings):
            if pygame.Rect(b[5], b[6], 350, 100).collidepoint(m_pos): is_h = True
            game.building(i, b[5], b[6])

        # Mod Butonu Çizimi (Yeni Yer)
        if game.mode_btn_rect.collidepoint(m_pos): is_h = True
        pygame.draw.rect(screen, "#333333", game.mode_btn_rect, border_radius=10)
        pygame.draw.rect(screen, "#ffffff", game.mode_btn_rect, 2, border_radius=10)
        mode_text = font_med.render(f"Buy: x{game.current_buy_amount}", True, "white")
        screen.blit(mode_text, (game.mode_btn_rect.x + 50, game.mode_btn_rect.y + 10))

        # Upgradeler
        ux, uy, count, h_upg = 15, 750, 0, None
        for u in game.upgrades:
            is_visible = (u[4] == -1 and game.m > u[2]*0.3) or \
                         (u[4] in [-2, -3, -4, -5] and game.click >= u[5]) or \
                         (u[4] >= 0 and game.buildings[u[4]][7] >= u[5])
            # ... çizim kodları ...
            if not u[3] and is_visible:
                ur = pygame.Rect(ux + (count%3)*115, uy + (count//3)*115, 100, 100)
                img = smallboximg.copy()
                if ur.collidepoint(m_pos):
                    is_h = True; h_upg = u; img.fill((60, 60, 60), special_flags=pygame.BLEND_RGB_ADD)
                screen.blit(img, ur); count += 1
                if count >= 9: break

        if game.golden_akif_active:
            if game.golden_akif_rect.collidepoint(m_pos): is_h = True
            g_img = pygame.transform.smoothscale(akif, (100, 100))
            g_img.fill((255, 215, 0), special_flags=pygame.BLEND_RGB_MULT)
            screen.blit(g_img, game.golden_akif_pos)

        if h_upg:
            screen.blit(boximg, (m_pos[0]+20, m_pos[1]+20))
            screen.blit(font_med.render(h_upg[0], True, "white"), (m_pos[0]+35, m_pos[1]+35))
            screen.blit(font_small.render(h_upg[1], True, "#929292"), (m_pos[0]+35, m_pos[1]+75))
            screen.blit(font_small.render(f"Cost: {compress(h_upg[2])}", True, "#15ff00"), (m_pos[0]+35, m_pos[1]+100))

        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND if is_h else pygame.SYSTEM_CURSOR_ARROW)
        for p in game.particles: p.draw(screen)
        pygame.display.flip()
        await asyncio.sleep(0)

if __name__ == "__main__": asyncio.run(main())