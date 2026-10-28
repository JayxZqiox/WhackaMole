import cv2
import mediapipe as mp
import pygame
import random
import numpy as np
import time
import math
import os
from collections import deque
import copy

# ================= INITIALIZE =================
pygame.init()
pygame.mixer.init()

# ---- Full HD ----
WIDTH, HEIGHT = 1920, 1080
GAME_WIDTH = 1150
CAM_WIDTH = WIDTH - GAME_WIDTH

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Whack Me: Neon Edition")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Verdana", 50, bold=True)
small_font = pygame.font.SysFont("Verdana", 24, bold=True)

# Sound
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sound_path = os.path.join(BASE_DIR, "dry-fart.wav")
try:
    whack_sound = pygame.mixer.Sound(sound_path)
except:
    whack_sound = None

# ================= MEDIA PIPE =================
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.8, min_tracking_confidence=0.8)
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)

# ================= SETTINGS =================
DIFFICULTY = {
    "easy": {"time": 30, "up_time": 1.8},
    "normal": {"time": 25, "up_time": 1.4},
    "hard": {"time": 20, "up_time": 1.0}
}

HARD_CAP_UP_TIME = 0.5 
HAND_DISTANCE_THRESH = 110
HAND_HISTORY_LEN = 5
MAX_SKILL_COOLDOWN = 800 

# ================= HOLES 9 GRID =================
hole_rows = [HEIGHT//2 - 120, HEIGHT//2, HEIGHT//2 + 120]
hole_cols = [GAME_WIDTH//2 - 280, GAME_WIDTH//2, GAME_WIDTH//2 + 280]
holes_positions = [(c, r) for r in hole_rows for c in hole_cols]

# ================= HELPERS =================
def load_highscore(diff):
    file = f"highscore_{diff}.txt"
    if os.path.exists(file):
        with open(file, "r") as f:
            try: return int(f.read())
            except: return 0
    return 0

def save_highscore(diff, score):
    highscore = load_highscore(diff)
    if score > highscore:
        with open(f"highscore_{diff}.txt", "w") as f: f.write(str(score))
        return score
    return highscore

# ================= UI DRAWING =================
def draw_scrolling_background(offset):
    screen.fill((10, 10, 25))
    for x in range(0, WIDTH, 80):
        pygame.draw.line(screen, (30, 45, 80), (x, 0), (x, HEIGHT), 1)
    for y in range(0, HEIGHT, 80):
        y_pos = (y + offset) % HEIGHT
        pygame.draw.line(screen, (40, 60, 110), (0, y_pos), (WIDTH, y_pos), 2)

def draw_cool_button(rect, text, is_hovered):
    bg_alpha = 70 if is_hovered else 30
    s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    s.fill((255, 255, 255, bg_alpha))
    screen.blit(s, (rect.x, rect.y))
    color = (255, 255, 255) if is_hovered else (180, 180, 180)
    pygame.draw.rect(screen, color, rect, 3, border_radius=12)
    text_surf = font.render(text, True, (255, 255, 255))
    screen.blit(text_surf, (rect.centerx - text_surf.get_width()//2, 
                            rect.centery - text_surf.get_height()//2))

def draw_hole(x, y):
    pygame.draw.ellipse(screen, (0, 255, 255), [x-65, y-25, 130, 50], 2)
    pygame.draw.ellipse(screen, (20, 20, 40), [x-60, y-20, 120, 40])

def draw_mole(x, y, angle=0, squeeze=1.0):
    mole_surf = pygame.Surface((80,80), pygame.SRCALPHA)
    pygame.draw.ellipse(mole_surf, (139,69,19),(0,20,80,50))
    pygame.draw.ellipse(mole_surf, (160,82,45),(0,0,80,50))
    pygame.draw.circle(mole_surf, (255,255,255),(25,25),8)
    pygame.draw.circle(mole_surf, (255,255,255),(55,25),8)
    pygame.draw.circle(mole_surf, (0,0,0),(25,25),4)
    pygame.draw.circle(mole_surf, (0,0,0),(55,25),4)
    mole_surf = pygame.transform.scale(mole_surf, (int(80*squeeze), int(80*(2-squeeze))))
    mole_surf = pygame.transform.rotate(mole_surf, angle)
    screen.blit(mole_surf,(x-40,y-40))

def draw_hammer(x, y, angle=0):
    hammer_surf = pygame.Surface((40,80), pygame.SRCALPHA)
    pygame.draw.rect(hammer_surf,(255,255,255),(14,20,12,60))
    pygame.draw.rect(hammer_surf,(200,200,200),(0,0,40,20))
    hammer_surf = pygame.transform.rotate(hammer_surf, angle)
    screen.blit(hammer_surf,(x-20,y-40))

def draw_star(x, y, alpha):
    star_surf = pygame.Surface((20,20), pygame.SRCALPHA)
    pygame.draw.polygon(star_surf,(255,255,255,int(alpha)),
                        [(10,0),(12,7),(20,7),(14,14),(16,20),
                         (10,15),(4,20),(6,14),(0,7),(8,7)])
    screen.blit(star_surf,(x-10,y-30))

def draw_hammer_trail(trail_points):
    for i, (x,y) in enumerate(trail_points):
        alpha = int(255*(i/len(trail_points)))
        pygame.draw.circle(screen, (255,255,255,alpha), (x,y), 8)

# ================= MENUS =================
def home_menu():
    bg_offset = 0
    while True:
        bg_offset += 2
        draw_scrolling_background(bg_offset)
        title = font.render("WHACK ME", True, (255,255,255))
        screen.blit(title,(WIDTH//2-title.get_width()//2, 200))
        start_btn = pygame.Rect(WIDTH//2-180,400,360,90)
        exit_btn = pygame.Rect(WIDTH//2-180,530,360,90)
        m_pos = pygame.mouse.get_pos()
        draw_cool_button(start_btn, "START GAME", start_btn.collidepoint(m_pos))
        draw_cool_button(exit_btn, "EXIT", exit_btn.collidepoint(m_pos))
        for event in pygame.event.get():
            if event.type==pygame.QUIT: pygame.quit(); exit()
            elif event.type==pygame.MOUSEBUTTONDOWN:
                if start_btn.collidepoint(event.pos): return "start"
                elif exit_btn.collidepoint(event.pos): pygame.quit(); exit()
        pygame.display.update()
        clock.tick(60)

def difficulty_menu():
    bg_offset = 0
    while True:
        bg_offset += 2
        draw_scrolling_background(bg_offset)
        title = font.render("DIFFICULTY", True,(255,255,255))
        screen.blit(title,(WIDTH//2-title.get_width()//2,150))
        btns = [
            (pygame.Rect(WIDTH//2-180,320,360,85), "EASY", "easy"),
            (pygame.Rect(WIDTH//2-180,430,360,85), "NORMAL", "normal"),
            (pygame.Rect(WIDTH//2-180,540,360,85), "HARD", "hard"),
            (pygame.Rect(WIDTH//2-180,650,360,85), "BACK", None)
        ]
        m_pos = pygame.mouse.get_pos()
        for rect, label, key in btns:
            draw_cool_button(rect, label, rect.collidepoint(m_pos))
        for event in pygame.event.get():
            if event.type==pygame.QUIT: pygame.quit(); exit()
            elif event.type==pygame.MOUSEBUTTONDOWN:
                for rect, label, key in btns:
                    if rect.collidepoint(event.pos): return key
        pygame.display.update()
        clock.tick(60)

# ================= GAME LOOP =================
def game_loop(settings, diff_name):
    score, combo, combo_timer = 0, 0, 0
    current_highscore = load_highscore(diff_name)
    remaining_time = settings["time"]
    mole_index = random.randint(0, len(holes_positions)-1)
    mole_up, mole_y_offset = True, 50
    last_toggle = time.time()
    stars = []
    
    hammer_x, hammer_y = WIDTH//2, HEIGHT//2
    hammer_angle, hammer_target_angle = 0, 0
    hammer_cooldown, last_whack_time = 0.15, 0 
    
    shake_offset_x, shake_offset_y = 0, 0
    shake_intensity, shake_duration = 0, 0
    hand_history = deque(maxlen=HAND_HISTORY_LEN)
    total_hits = 0

    special_available, special_active = True, False
    special_timer, special_cooldown_timer = 0, 0
    open_hand_frames = 0 # Safety counter to prevent accidental skill triggers

    speed_increase = 0.01 if diff_name == "easy" else 0.02 if diff_name == "normal" else 0.03

    while True:
        if shake_duration > 0:
            shake_offset_x = random.randint(-shake_intensity, shake_intensity)
            shake_offset_y = random.randint(-shake_intensity, shake_intensity)
            shake_duration -= 1
        else:
            shake_offset_x, shake_offset_y = 0, 0

        draw_scrolling_background(pygame.time.get_ticks() // 10)
        
        # Game Board
        pygame.draw.rect(screen, (10,10,30), (0,0, GAME_WIDTH, HEIGHT))
        for hx, hy in holes_positions: draw_hole(hx+shake_offset_x, hy+shake_offset_y)
        
        # Side Panel
        pygame.draw.rect(screen, (20,20,50), (GAME_WIDTH, 0, CAM_WIDTH, HEIGHT))
        pygame.draw.rect(screen, (255,255,255), (GAME_WIDTH+10, 10, CAM_WIDTH-20, HEIGHT-20), 2, border_radius=10)

        # --- MEDIA PIPE LOGIC ---
        ret, frame = cap.read()
        hand_closed = False
        hand_fully_open = False
        
        if ret:
            frame = cv2.flip(frame, 1)
            results = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if results.multi_hand_landmarks:
                handLms = results.multi_hand_landmarks[0]
                target_hx = int(handLms.landmark[8].x * GAME_WIDTH)
                target_hy = int(handLms.landmark[8].y * HEIGHT)
                hammer_x += (target_hx - hammer_x) * 0.7 
                hammer_y += (target_hy - hammer_y) * 0.7
                hand_history.append((int(hammer_x), int(hammer_y)))
                
                # Check for 5 fingers open (Skill trigger)
                tips = [8, 12, 16, 20]
                up_count = sum([1 for tip in tips if handLms.landmark[tip].y < handLms.landmark[tip-2].y])
                # Special check for thumb (landmark 4 vs 3)
                if handLms.landmark[4].x < handLms.landmark[3].x: up_count += 1
                
                hand_fully_open = up_count >= 5
                
                # Check for closed fist (Whack trigger)
                down_count = sum([1 for tip in tips if handLms.landmark[tip].y > handLms.landmark[tip-2].y])
                hand_closed = down_count >= 3

        # Skill logic with frame-buffer to prevent misfires
        if hand_fully_open and special_available:
            open_hand_frames += 1
            if open_hand_frames > 6: # Must hold open for 6 frames (~0.1 seconds)
                special_active, special_available = True, False
                special_timer, special_cooldown_timer = 240, MAX_SKILL_COOLDOWN
                open_hand_frames = 0
        else:
            open_hand_frames = 0

        if special_active:
            special_timer -= 1
            if special_timer <= 0:
                special_active = False
                last_toggle = time.time()
        
        if not special_available and special_cooldown_timer > 0:
            special_cooldown_timer -= 1
            if special_cooldown_timer <= 0: special_available = True

        # --- COLLISION ---
        mole_x, mole_y = holes_positions[mole_index]
        velocity = hand_history[-1][1] - hand_history[0][1] if len(hand_history) >= 2 else 0

        if mole_up and hand_closed and abs(velocity) > 2:
            if math.hypot(hammer_x - mole_x, hammer_y - (mole_y - mole_y_offset)) < HAND_DISTANCE_THRESH:
                if time.time() - last_whack_time > hammer_cooldown:
                    last_whack_time = time.time()
                    hammer_target_angle = -60
                    stars.append({'x': mole_x, 'y': mole_y-50, 'alpha': 255})
                    score += 1 + combo
                    combo += 1
                    combo_timer = time.time()
                    if whack_sound: whack_sound.play()
                    shake_intensity, shake_duration, total_hits = 15, 10, total_hits + 1
                    
                    if total_hits % 5 == 0:
                        settings['up_time'] = max(settings['up_time'] - speed_increase, HARD_CAP_UP_TIME)

                    if not special_active:
                        mole_up = False 

        # Visuals
        mole_target_offset = 50 if mole_up else 0
        mole_y_offset += (mole_target_offset - mole_y_offset) * 0.4
        hammer_angle += (hammer_target_angle - hammer_angle) * 0.5
        if abs(hammer_angle - hammer_target_angle) < 1: hammer_target_angle = 0

        if not special_active:
            if not mole_up or (time.time() - last_toggle > settings['up_time']):
                mole_index = random.choice([i for i in range(len(holes_positions)) if i != mole_index])
                mole_up = True
                last_toggle = time.time()
                mole_y_offset = 0 
        else:
            if pygame.time.get_ticks() % 500 < 250:
                freeze_txt = font.render("FREEZE!", True, (0, 255, 255))
                screen.blit(freeze_txt, (mole_x - freeze_txt.get_width()//2, mole_y - 120))

        remaining_time -= (1/60)
        remaining_time = max(0, remaining_time)

        draw_mole(mole_x+shake_offset_x, mole_y-mole_y_offset+shake_offset_y, 0)
        draw_hammer_trail(hand_history)
        draw_hammer(hammer_x+shake_offset_x, hammer_y+shake_offset_y, hammer_angle)

        for s in stars[:]:
            draw_star(s['x']+shake_offset_x, s['y']+shake_offset_y, s['alpha'])
            s['y'] -= 2; s['alpha'] -= 7
            if s['alpha'] <= 0: stars.remove(s)

        if combo > 0 and time.time() - combo_timer > 2: combo = 0

        # --- HUD SIDE PANEL ---
        hud_x = GAME_WIDTH + 60
        hud_y = 100
        stats = [
            (f"TIME: {int(remaining_time)}", (255, 255, 255)),
            (f"SCORE: {score}", (0, 255, 100)),
            (f"HIGH: {max(score, current_highscore)}", (255, 200, 0)),
            (f"COMBO: x{combo}", (255, 100, 255))
        ]
        for i, (txt, color) in enumerate(stats):
            screen.blit(font.render(txt, True, color), (hud_x, hud_y + i*80))
        
        # --- SKILL HUD & COOLDOWN BAR ---
        bar_y = hud_y + 450 
        MAX_BAR_WIDTH = 400 
        bar_x = hud_x 
        
        if special_available:
            msg = "SKILL: READY (OPEN HAND)"
            color = (0, 255, 255)
            progress = 1.0
        elif special_active:
            msg = "SKILL: ACTIVE!"
            color = (255, 255, 0)
            progress = special_timer / 240
        else:
            msg = f"SKILL CHARGING..."
            color = (255, 50, 50)
            progress = (MAX_SKILL_COOLDOWN - special_cooldown_timer) / MAX_SKILL_COOLDOWN

        screen.blit(small_font.render(msg, True, color), (bar_x, bar_y - 40))
        pygame.draw.rect(screen, (40, 40, 70), (bar_x, bar_y, MAX_BAR_WIDTH, 25), border_radius=10)
        if progress > 0:
            pygame.draw.rect(screen, color, (bar_x, bar_y, int(MAX_BAR_WIDTH * progress), 25), border_radius=10)
        pygame.draw.rect(screen, color, (bar_x, bar_y, MAX_BAR_WIDTH, 25), 2, border_radius=10)

        if remaining_time <= 0:
            save_highscore(diff_name, score)
            while True:
                draw_scrolling_background(0)
                msg = font.render(f"FINAL SCORE: {score}", True, (255,255,255))
                screen.blit(msg, (WIDTH//2-msg.get_width()//2, HEIGHT//2-100))
                restart_btn = pygame.Rect(WIDTH//2-180, HEIGHT//2+50, 360, 90)
                back_btn = pygame.Rect(WIDTH//2-180, HEIGHT//2+160, 360, 90)
                m_pos = pygame.mouse.get_pos()
                draw_cool_button(restart_btn, "RESTART", restart_btn.collidepoint(m_pos))
                draw_cool_button(back_btn, "MENU", back_btn.collidepoint(m_pos))
                for event in pygame.event.get():
                    if event.type==pygame.QUIT: pygame.quit(); exit()
                    if event.type==pygame.MOUSEBUTTONDOWN:
                        if restart_btn.collidepoint(event.pos): return "restart"
                        if back_btn.collidepoint(event.pos): return "back"
                pygame.display.update()
                clock.tick(60)

        pygame.display.update()
        clock.tick(60)

# ================= MAIN =================
while True:
    action = home_menu()
    if action == "start":
        diff = difficulty_menu()
        if diff:
            while True:
                res = game_loop(copy.deepcopy(DIFFICULTY[diff]), diff)
                if res != "restart": break































import cv2
import mediapipe as mp
import pygame
import random
import numpy as np
import time
import math
import os
from collections import deque
import copy

# ================= INITIALIZE =================
pygame.init()
pygame.mixer.init()

# ---- Full HD ----
WIDTH, HEIGHT = 1920, 1080
GAME_WIDTH = 1150
CAM_WIDTH = WIDTH - GAME_WIDTH

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Whack Me: Blade Storm Edition")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Verdana", 50, bold=True)
small_font = pygame.font.SysFont("Verdana", 24, bold=True)

# Sound
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sound_path = os.path.join(BASE_DIR, "dry-fart.wav")
slice_sound = pygame.mixer.Sound('slice.wav')
try:
    whack_sound = pygame.mixer.Sound(sound_path)
except:
    whack_sound = None

# ================= MEDIA PIPE =================
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.8, min_tracking_confidence=0.8)
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)

# ================= SETTINGS =================
DIFFICULTY = {
    "easy": {"time": 30, "up_time": 1.8},
    "normal": {"time": 25, "up_time": 1.4},
    "hard": {"time": 20, "up_time": 1.0}
}

HARD_CAP_UP_TIME = 0.5 
HAND_DISTANCE_THRESH = 110
HAND_HISTORY_LEN = 8
MAX_SKILL_COOLDOWN = 800 
MAX_SLICE_COOLDOWN = 600  # Cooldown for the Blade skill

# ================= HOLES 9 GRID =================
hole_rows = [HEIGHT//2 - 120, HEIGHT//2, HEIGHT//2 + 120]
hole_cols = [GAME_WIDTH//2 - 280, GAME_WIDTH//2, GAME_WIDTH//2 + 280]
holes_positions = [(c, r) for r in hole_rows for c in hole_cols]

# ================= HELPERS =================
def load_highscore(diff):
    file = f"highscore_{diff}.txt"
    if os.path.exists(file):
        with open(file, "r") as f:
            try: return int(f.read())
            except: return 0
    return 0

def save_highscore(diff, score):
    highscore = load_highscore(diff)
    if score > highscore:
        with open(f"highscore_{diff}.txt", "w") as f: f.write(str(score))
        return score
    return highscore

# ================= UI DRAWING =================
def draw_scrolling_background(offset):
    screen.fill((10, 10, 25))
    for x in range(0, WIDTH, 80):
        pygame.draw.line(screen, (30, 45, 80), (x, 0), (x, HEIGHT), 1)
    for y in range(0, HEIGHT, 80):
        y_pos = (y + offset) % HEIGHT
        pygame.draw.line(screen, (40, 60, 110), (0, y_pos), (WIDTH, y_pos), 2)

def draw_cool_button(rect, text, is_hovered):
    bg_alpha = 70 if is_hovered else 30
    s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    s.fill((255, 255, 255, bg_alpha))
    screen.blit(s, (rect.x, rect.y))
    color = (255, 255, 255) if is_hovered else (180, 180, 180)
    pygame.draw.rect(screen, color, rect, 3, border_radius=12)
    text_surf = font.render(text, True, (255, 255, 255))
    screen.blit(text_surf, (rect.centerx - text_surf.get_width()//2, 
                            rect.centery - text_surf.get_height()//2))

def draw_hole(x, y):
    pygame.draw.ellipse(screen, (0, 255, 255), [x-65, y-25, 130, 50], 2)
    pygame.draw.ellipse(screen, (20, 20, 40), [x-60, y-20, 120, 40])

def draw_mole(x, y, angle=0, squeeze=1.0, is_sliced=False):
    if is_sliced:
        # Draw sliced halves sliding apart
        pygame.draw.ellipse(screen, (139,69,19), (x-55, y-20, 40, 40)) # Left piece
        pygame.draw.ellipse(screen, (139,69,19), (x+15, y-20, 40, 40)) # Right piece
        # Some "inner" mole color
        pygame.draw.ellipse(screen, (200,100,80), (x-40, y-15, 20, 30))
        pygame.draw.ellipse(screen, (200,100,80), (x+20, y-15, 20, 30))
    else:
        mole_surf = pygame.Surface((80,80), pygame.SRCALPHA)
        pygame.draw.ellipse(mole_surf, (139,69,19),(0,20,80,50))
        pygame.draw.ellipse(mole_surf, (160,82,45),(0,0,80,50))
        pygame.draw.circle(mole_surf, (255,255,255),(25,25),8)
        pygame.draw.circle(mole_surf, (255,255,255),(55,25),8)
        pygame.draw.circle(mole_surf, (0,0,0),(25,25),4)
        pygame.draw.circle(mole_surf, (0,0,0),(55,25),4)
        mole_surf = pygame.transform.scale(mole_surf, (int(80*squeeze), int(80*(2-squeeze))))
        mole_surf = pygame.transform.rotate(mole_surf, angle)
        screen.blit(mole_surf,(x-40,y-40))

def draw_hammer(x, y, angle=0, status="FIST", slice_active=False):
    if slice_active:
        # Draw Neon Blade
        pygame.draw.line(screen, (255, 0, 255), (x-40, y-40), (x+40, y+40), 10)
        pygame.draw.line(screen, (255, 255, 255), (x-35, y-35), (x+35, y+35), 3)
    else:
        hammer_surf = pygame.Surface((40,80), pygame.SRCALPHA)
        pygame.draw.rect(hammer_surf,(255,255,255),(14,20,12,60))
        pygame.draw.rect(hammer_surf,(200,200,200),(0,0,40,20))
        hammer_surf = pygame.transform.rotate(hammer_surf, angle)
        screen.blit(hammer_surf,(x-20,y-40))

def draw_blood(particles):
    for p in particles:
        pygame.draw.circle(screen, (200, 0, 0), (int(p['x']), int(p['y'])), p['size'])
        p['x'] += p['vx']
        p['y'] += p['vy']
        p['vy'] += 0.2 # Gravity
        p['life'] -= 1

def draw_hammer_trail(trail_points, slice_active=False):
    for i, (x,y) in enumerate(trail_points):
        alpha = int(255*(i/len(trail_points)))
        color = (255, 0, 255) if slice_active else (255, 255, 255)
        pygame.draw.circle(screen, color + (alpha,), (x,y), 8 if slice_active else 5)

# ================= MENUS =================
def home_menu():
    bg_offset = 0
    while True:
        bg_offset += 2
        draw_scrolling_background(bg_offset)
        title = font.render("WHACK ME", True, (255,255,255))
        screen.blit(title,(WIDTH//2-title.get_width()//2, 200))
        start_btn = pygame.Rect(WIDTH//2-180,400,360,90)
        exit_btn = pygame.Rect(WIDTH//2-180,530,360,90)
        m_pos = pygame.mouse.get_pos()
        draw_cool_button(start_btn, "START GAME", start_btn.collidepoint(m_pos))
        draw_cool_button(exit_btn, "EXIT", exit_btn.collidepoint(m_pos))
        for event in pygame.event.get():
            if event.type==pygame.QUIT: pygame.quit(); exit()
            elif event.type==pygame.MOUSEBUTTONDOWN:
                if start_btn.collidepoint(event.pos): return "start"
                elif exit_btn.collidepoint(event.pos): pygame.quit(); exit()
        pygame.display.update()
        clock.tick(60)

def difficulty_menu():
    bg_offset = 0
    while True:
        bg_offset += 2
        draw_scrolling_background(bg_offset)
        title = font.render("DIFFICULTY", True,(255,255,255))
        screen.blit(title,(WIDTH//2-title.get_width()//2,150))
        btns = [
            (pygame.Rect(WIDTH//2-180,320,360,85), "EASY", "easy"),
            (pygame.Rect(WIDTH//2-180,430,360,85), "NORMAL", "normal"),
            (pygame.Rect(WIDTH//2-180,540,360,85), "HARD", "hard"),
            (pygame.Rect(WIDTH//2-180,650,360,85), "BACK", None)
        ]
        m_pos = pygame.mouse.get_pos()
        for rect, label, key in btns:
            draw_cool_button(rect, label, rect.collidepoint(m_pos))
        for event in pygame.event.get():
            if event.type==pygame.QUIT: pygame.quit(); exit()
            elif event.type==pygame.MOUSEBUTTONDOWN:
                for rect, label, key in btns:
                    if rect.collidepoint(event.pos): return key
        pygame.display.update()
        clock.tick(60)

# ================= GAME LOOP =================
def game_loop(settings, diff_name):
    score, combo, combo_timer = 0, 0, 0
    current_highscore = load_highscore(diff_name)
    remaining_time = settings["time"]
    mole_index = random.randint(0, len(holes_positions)-1)
    mole_up, mole_y_offset = True, 50
    last_toggle = time.time()
    
    hammer_x, hammer_y = WIDTH//2, HEIGHT//2
    hammer_angle, hammer_target_angle = 0, 0
    hammer_cooldown, last_whack_time = 0.15, 0 
    
    shake_offset_x, shake_offset_y = 0, 0
    shake_intensity, shake_duration = 0, 0
    hand_history = deque(maxlen=HAND_HISTORY_LEN)
    blood_particles = []

    # Skills State
    freeze_available, freeze_active = True, False
    freeze_timer, freeze_cd_timer = 0, 0
    
    slice_available, slice_active = True, False
    slice_timer, slice_cd_timer = 0, 0
    
    hand_status = "NONE"
    is_sliced = False

    speed_increase = 0.01 if diff_name == "easy" else 0.02 if diff_name == "normal" else 0.03

    while True:
        if shake_duration > 0:
            shake_offset_x = random.randint(-shake_intensity, shake_intensity)
            shake_offset_y = random.randint(-shake_intensity, shake_intensity)
            shake_duration -= 1
        else:
            shake_offset_x, shake_offset_y = 0, 0

        draw_scrolling_background(pygame.time.get_ticks() // 10)
        
        # Game Board
        pygame.draw.rect(screen, (10,10,30), (0,0, GAME_WIDTH, HEIGHT))
        for hx, hy in holes_positions: draw_hole(hx+shake_offset_x, hy+shake_offset_y)
        
        # Side Panel
        pygame.draw.rect(screen, (20,20,50), (GAME_WIDTH, 0, CAM_WIDTH, HEIGHT))
        pygame.draw.rect(screen, (255,255,255), (GAME_WIDTH+10, 10, CAM_WIDTH-20, HEIGHT-20), 2, border_radius=10)

        # --- MEDIA PIPE LOGIC ---
        ret, frame = cap.read()
        hand_closed = False
        hand_fully_open = False
        hand_one_finger = False
        
        if ret:
            frame = cv2.flip(frame, 1)
            results = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if results.multi_hand_landmarks:
                handLms = results.multi_hand_landmarks[0]
                target_hx = int(handLms.landmark[8].x * GAME_WIDTH)
                target_hy = int(handLms.landmark[8].y * HEIGHT)
                hammer_x += (target_hx - hammer_x) * 0.7 
                hammer_y += (target_hy - hammer_y) * 0.7
                hand_history.append((int(hammer_x), int(hammer_y)))
                
                tips = [8, 12, 16, 20]
                up_states = [handLms.landmark[tip].y < handLms.landmark[tip-2].y for tip in tips]
                thumb_up = handLms.landmark[4].x < handLms.landmark[3].x
                up_count = sum(up_states) + (1 if thumb_up else 0)

                if up_count == 0:
                    hand_closed = True; hand_status = "FIST"
                elif up_states[0] and sum(up_states) == 1 and not thumb_up:
                    hand_one_finger = True; hand_status = "SLICE"
                elif up_count >= 5:
                    hand_fully_open = True; hand_status = "OPEN"
                else:
                    hand_status = "MOVING"

        # --- SKILL LOGIC ---
        # Skill 1: Freeze (Open Hand)
        if hand_fully_open and freeze_available:
            freeze_active, freeze_available = True, False
            freeze_timer, freeze_cd_timer = 240, MAX_SKILL_COOLDOWN
        
        if freeze_active:
            freeze_timer -= 1
            if freeze_timer <= 0: freeze_active = False; last_toggle = time.time()
        elif not freeze_available:
            freeze_cd_timer -= 1
            if freeze_cd_timer <= 0: freeze_available = True

        # Skill 2: Blade Storm (1 Finger)
        if hand_one_finger and slice_available:
            slice_active, slice_available = True, False
            slice_timer, slice_cd_timer = 180, MAX_SLICE_COOLDOWN
        
        if slice_active:
            slice_timer -= 1
            if slice_timer <= 0: slice_active = False
        elif not slice_available:
            slice_cd_timer -= 1
            if slice_cd_timer <= 0: slice_available = True

        # --- COMBAT LOGIC ---
        mole_x, mole_y = holes_positions[mole_index]
        dist = math.hypot(hammer_x - mole_x, hammer_y - (mole_y - mole_y_offset))

        # WHACK logic
        if mole_up and hand_closed and dist < HAND_DISTANCE_THRESH:
            if len(hand_history) > 2 and hand_history[-1][1] - hand_history[0][1] > 4:
                if time.time() - last_whack_time > hammer_cooldown:
                    last_whack_time = time.time()
                    hammer_target_angle = -60
                    score += 1 + combo
                    combo += 1
                    combo_timer = time.time()
                    if whack_sound: whack_sound.play()
                    shake_intensity, shake_duration = 15, 10
                    if not freeze_active: mole_up = False 

        # SLICE logic
        if mole_up and slice_active and dist < 80:
            is_sliced = True
            score += 3 # Slicing is worth more!
            combo += 1
            combo_timer = time.time()

            if slice_sound: slice_sound.play()
            shake_intensity, shake_duration = 20, 12
            # Create blood particles
            for _ in range(15):
                blood_particles.append({'x': mole_x, 'y': mole_y, 'vx': random.uniform(-6, 6), 
                                        'vy': random.uniform(-8, 2), 'life': 30, 'size': random.randint(4, 8)})
            if not freeze_active: mole_up = False

        # --- UPDATES ---
        mole_target_offset = 50 if mole_up else 0
        mole_y_offset += (mole_target_offset - mole_y_offset) * 0.4
        hammer_angle += (hammer_target_angle - hammer_angle) * 0.5
        if abs(hammer_angle - hammer_target_angle) < 1: hammer_target_angle = 0

        if not freeze_active:
            if not mole_up or (time.time() - last_toggle > settings['up_time']):
                mole_index = random.choice([i for i in range(len(holes_positions)) if i != mole_index])
                mole_up, is_sliced = True, False
                last_toggle = time.time()
                mole_y_offset = 0 

        remaining_time -= (1/60)
        remaining_time = max(0, remaining_time)

        # --- DRAWING ---
        draw_mole(mole_x+shake_offset_x, mole_y-mole_y_offset+shake_offset_y, 0, is_sliced=is_sliced)
        draw_blood(blood_particles)
        blood_particles = [p for p in blood_particles if p['life'] > 0]
        
        draw_hammer_trail(hand_history, slice_active)
        draw_hammer(hammer_x+shake_offset_x, hammer_y+shake_offset_y, hammer_angle, slice_active=slice_active)
        
        status_color = (255,50,50) if hand_status == "FIST" else (255,0,255) if hand_status == "SLICE" else (0,255,255)
        screen.blit(small_font.render(f"[{hand_status}]", True, status_color), (hammer_x + 30, hammer_y - 30))

        if combo > 0 and time.time() - combo_timer > 2: combo = 0

        # HUD Side Panel
        hud_x, hud_y = GAME_WIDTH + 60, 80
        stats = [(f"TIME: {int(remaining_time)}", (255, 255, 255)), (f"SCORE: {score}", (0, 255, 100)),
                 (f"HIGH: {max(score, current_highscore)}", (255, 200, 0)), (f"COMBO: x{combo}", (255, 100, 255))]
        for i, (txt, color) in enumerate(stats):
            screen.blit(font.render(txt, True, color), (hud_x, hud_y + i*80))
        
        # Skill 1 Bar (Freeze)
        f_bar_y = 480
        f_progress = freeze_timer/240 if freeze_active else (MAX_SKILL_COOLDOWN - freeze_cd_timer)/MAX_SKILL_COOLDOWN
        pygame.draw.rect(screen, (40, 40, 70), (hud_x, f_bar_y, 400, 25), border_radius=10)
        pygame.draw.rect(screen, (0, 255, 255), (hud_x, f_bar_y, int(400 * f_progress), 25), border_radius=10)
        screen.blit(small_font.render("FREEZE (OPEN HAND)", True, (255,255,255)), (hud_x, f_bar_y - 35))

        # Skill 2 Bar (Blade Storm)
        s_bar_y = 600
        s_progress = slice_timer/180 if slice_active else (MAX_SLICE_COOLDOWN - slice_cd_timer)/MAX_SLICE_COOLDOWN
        pygame.draw.rect(screen, (40, 40, 70), (hud_x, s_bar_y, 400, 25), border_radius=10)
        pygame.draw.rect(screen, (255, 0, 255), (hud_x, s_bar_y, int(400 * s_progress), 25), border_radius=10)
        screen.blit(small_font.render("BLADE STORM (1 FINGER)", True, (255,255,255)), (hud_x, s_bar_y - 35))

        if remaining_time <= 0:
            save_highscore(diff_name, score)
            return "back"

        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); exit()

        pygame.display.update()
        clock.tick(60)

# ================= MAIN =================
while True:
    action = home_menu()
    if action == "start":
        diff = difficulty_menu()
        if diff:
            while True:
                res = game_loop(copy.deepcopy(DIFFICULTY[diff]), diff)
                if res != "restart": break


























import cv2
import mediapipe as mp
import pygame
import random
import numpy as np
import time
import math
import os
from collections import deque
import copy

# ================= INITIALIZE =================
pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=1)

WIDTH, HEIGHT = 1920, 1080
GAME_WIDTH = 1150
CAM_WIDTH = WIDTH - GAME_WIDTH

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Whack Me: Hardcore Arcade Edition")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Verdana", 50, bold=True)
big_font = pygame.font.SysFont("Verdana", 100, bold=True)
giant_font = pygame.font.SysFont("Verdana", 160, bold=True) 
small_font = pygame.font.SysFont("Verdana", 24, bold=True)

# --- Procedural Sound Generator ---
def generate_beep(freq=1000, duration=0.1):
    sample_rate = 44100
    n_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, n_samples, False)
    wave = np.sin(2 * np.pi * freq * t) * 32767
    wave = wave.astype(np.int16)
    return pygame.mixer.Sound(buffer=wave)

warning_beep = generate_beep(1500, 0.1)
bonus_sound = generate_beep(2000, 0.05) 

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    whack_sound = pygame.mixer.Sound(os.path.join(BASE_DIR, "dry-fart.wav"))
    slice_sound = pygame.mixer.Sound('slice.wav')
except:
    whack_sound = slice_sound = None

# ================= MEDIA PIPE =================
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.8, min_tracking_confidence=0.8)
cap = cv2.VideoCapture(0)

# ================= SETTINGS =================
DIFFICULTY = {
    "easy": {"time": 30, "up_time": 1.8, "hardcore": False},
    "normal": {"time": 25, "up_time": 1.4, "hardcore": False},
    "hard": {"time": 20, "up_time": 1.0, "hardcore": False},
    "hardcore": {"time": 20, "up_time": 1.5, "hardcore": True} 
}
HAND_DISTANCE_THRESH = 110
HAND_HISTORY_LEN = 8
MAX_SKILL_COOLDOWN = 800 
MAX_SLICE_COOLDOWN = 600  

hole_rows = [HEIGHT//2 - 120, HEIGHT//2, HEIGHT//2 + 120]
hole_cols = [GAME_WIDTH//2 - 280, GAME_WIDTH//2, GAME_WIDTH//2 + 280]
holes_positions = [(c, r) for r in hole_rows for c in hole_cols]

# ================= HELPERS =================
def load_highscore(diff):
    file = f"highscore_{diff}.txt"
    if os.path.exists(file):
        with open(file, "r") as f:
            try: return int(f.read())
            except: return 0
    return 0

def save_highscore(diff, score):
    hs = load_highscore(diff)
    if score > hs:
        with open(f"highscore_{diff}.txt", "w") as f: f.write(str(score))
        return score
    return hs

# ================= UI DRAWING =================
def draw_scrolling_background(offset, is_hardcore=False):
    bg_color = (25, 10, 10) if is_hardcore else (10, 10, 25)
    line_color = (60, 20, 20) if is_hardcore else (30, 45, 80)
    screen.fill(bg_color)
    for x in range(0, WIDTH, 80):
        pygame.draw.line(screen, line_color, (x, 0), (x, HEIGHT), 1)
    for y in range(0, HEIGHT, 80):
        y_pos = (y + offset) % HEIGHT
        pygame.draw.line(screen, line_color, (0, y_pos), (WIDTH, y_pos), 2)

def draw_cool_button(rect, text, is_hovered):
    bg_alpha = 70 if is_hovered else 30
    s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    s.fill((255, 255, 255, bg_alpha))
    screen.blit(s, (rect.x, rect.y))
    color = (255, 255, 255) if is_hovered else (180, 180, 180)
    pygame.draw.rect(screen, color, rect, 3, border_radius=12)
    text_surf = font.render(text, True, (255, 255, 255))
    screen.blit(text_surf, (rect.centerx - text_surf.get_width()//2, rect.centery - text_surf.get_height()//2))

def draw_hole(x, y):
    pygame.draw.ellipse(screen, (0, 255, 255), [x-65, y-25, 130, 50], 2)
    pygame.draw.ellipse(screen, (20, 20, 40), [x-60, y-20, 120, 40])

def draw_mole(x, y, is_sliced=False, is_hit=False):
    squish = 25 if is_hit else 0
    if is_sliced:
        pygame.draw.ellipse(screen, (139,69,19), (x-55, y-20, 40, 40)) 
        pygame.draw.ellipse(screen, (139,69,19), (x+15, y-20, 40, 40)) 
    else:
        mole_surf = pygame.Surface((80,80), pygame.SRCALPHA)
        pygame.draw.ellipse(mole_surf, (139,69,19),(0,20+squish,80,50-squish))
        pygame.draw.ellipse(mole_surf, (160,82,45),(0,squish,80,50-squish))
        pygame.draw.circle(mole_surf, (255,255,255),(25,25+squish), 8)
        pygame.draw.circle(mole_surf, (255,255,255),(55,25+squish), 8)
        screen.blit(mole_surf,(x-40,y-40))

def draw_hammer(x, y, angle=0, slice_active=False):
    if slice_active:
        pygame.draw.line(screen, (255, 0, 255), (x-45, y-45), (x+45, y+45), 12)
        pygame.draw.line(screen, (255, 255, 255), (x-40, y-40), (x+40, y+40), 4)
    else:
        hammer_surf = pygame.Surface((40,80), pygame.SRCALPHA)
        pygame.draw.rect(hammer_surf,(255,255,255),(14,20,12,60)) 
        pygame.draw.rect(hammer_surf,(200,200,200),(0,0,40,25), border_radius=3) 
        rotated = pygame.transform.rotate(hammer_surf, angle)
        screen.blit(rotated,(x-rotated.get_width()//2, y-rotated.get_height()//2))

def draw_particles(particles, color=(200, 0, 0)):
    for p in particles:
        pygame.draw.circle(screen, color, (int(p['x']), int(p['y'])), p['size'])
        p['x'] += p['vx']; p['y'] += p['vy']; p['vy'] += 0.2; p['life'] -= 1

def draw_hammer_trail(trail_points, slice_active=False):
    for i, (x,y) in enumerate(trail_points):
        alpha = int(255*(i/len(trail_points)))
        color = (255, 0, 255) if slice_active else (255, 255, 255)
        pygame.draw.circle(screen, color + (alpha,), (x,y), 8 if slice_active else 5)

# ================= MENUS =================
def game_over_screen(final_score, diff):
    high_score = save_highscore(diff, final_score)
    while True:
        draw_scrolling_background(pygame.time.get_ticks() // 10, diff=="hardcore")
        title = big_font.render("GAME OVER", True, (255, 50, 50))
        sc_txt = font.render(f"SCORE: {final_score}", True, (255, 255, 255))
        hs_txt = font.render(f"HIGH SCORE: {high_score}", True, (0, 255, 200))
        hint = small_font.render("Click anywhere to continue", True, (150, 150, 150))
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 250))
        screen.blit(sc_txt, (WIDTH//2 - sc_txt.get_width()//2, 400))
        screen.blit(hs_txt, (WIDTH//2 - hs_txt.get_width()//2, 480))
        screen.blit(hint, (WIDTH//2 - hint.get_width()//2, 650))
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); exit()
            if event.type == pygame.MOUSEBUTTONDOWN: return
        pygame.display.update(); clock.tick(60)

def home_menu():
    bg_offset = 0
    while True:
        bg_offset += 2
        draw_scrolling_background(bg_offset)
        title = font.render("WHACK ME", True, (255,255,255))
        screen.blit(title,(WIDTH//2-title.get_width()//2, 200))
        start_btn, exit_btn = pygame.Rect(WIDTH//2-180,400,360,90), pygame.Rect(WIDTH//2-180,530,360,90)
        m_pos = pygame.mouse.get_pos()
        draw_cool_button(start_btn, "START GAME", start_btn.collidepoint(m_pos))
        draw_cool_button(exit_btn, "EXIT", exit_btn.collidepoint(m_pos))
        for event in pygame.event.get():
            if event.type==pygame.QUIT: pygame.quit(); exit()
            elif event.type==pygame.MOUSEBUTTONDOWN:
                if start_btn.collidepoint(event.pos): return "start"
                elif exit_btn.collidepoint(event.pos): pygame.quit(); exit()
        pygame.display.update(); clock.tick(60)

def difficulty_menu():
    bg_offset = 0
    while True:
        bg_offset += 2
        draw_scrolling_background(bg_offset)
        btns = [(pygame.Rect(WIDTH//2-180,210,360,85), "EASY", "easy"),
                (pygame.Rect(WIDTH//2-180,310,360,85), "NORMAL", "normal"),
                (pygame.Rect(WIDTH//2-180,410,360,85), "HARD", "hard"),
                (pygame.Rect(WIDTH//2-180,510,360,85), "HARDCORE", "hardcore"),
                (pygame.Rect(WIDTH//2-180,610,360,85), "BACK", None)]
        m_pos = pygame.mouse.get_pos()
        for rect, label, key in btns: 
            draw_cool_button(rect, label, rect.collidepoint(m_pos))
        for event in pygame.event.get():
            if event.type==pygame.QUIT: pygame.quit(); exit()
            elif event.type==pygame.MOUSEBUTTONDOWN:
                for rect, label, key in btns:
                    if rect.collidepoint(event.pos): return key
        pygame.display.update(); clock.tick(60)

# ================= GAME LOOP =================
def game_loop(settings, diff_name):
    score, combo, combo_timer = 0, 0, 0
    current_highscore = load_highscore(diff_name)
    remaining_time = settings["time"]
    mole_index = random.randint(0, len(holes_positions)-1)
    mole_up, mole_y_offset, last_toggle, last_beep_time = True, 50, time.time(), -1
    hammer_x, hammer_y, hammer_angle, hammer_target_angle = WIDTH//2, HEIGHT//2, 0, 0
    hit_anim_timer, last_whack_time = 0, 0 
    hand_history = deque(maxlen=HAND_HISTORY_LEN)
    blood_particles, spark_particles = [], []

    shake_intensity = 0
    flash_alpha = 0
    float_texts = [] 

    freeze_available, freeze_active, freeze_timer, freeze_cd_timer = True, False, 0, 0
    slice_available, slice_active, slice_timer, slice_cd_timer = True, False, 0, 0
    hand_status, is_sliced = "MOVING", False

    while True:
        # --- Time Logic ---
        time_speed = 1.0
        if settings['hardcore']:
            # The higher the score, the faster the clock drains
            time_speed = 1.0 + (score * 0.006) 
        
        # In Freeze mode, time doesn't drain
        if not freeze_active:
            remaining_time -= (1/60) * time_speed
            
        current_sec = int(math.ceil(remaining_time))

        # --- Speed Scaling (Score Based) ---
        current_up_time = settings['up_time']
        if settings['hardcore']:
            speed_penalty = score * 0.012
            current_up_time = max(0.25, settings['up_time'] - speed_penalty)

        if remaining_time <= 5.9 and current_sec != last_beep_time and current_sec >= 1:
            if warning_beep: warning_beep.play()
            last_beep_time = current_sec

        offset_x, offset_y = 0, 0
        if shake_intensity > 0:
            offset_x = random.randint(-shake_intensity, shake_intensity)
            offset_y = random.randint(-shake_intensity, shake_intensity)
            shake_intensity -= 1

        draw_scrolling_background(pygame.time.get_ticks() // 10, settings['hardcore'])
        pygame.draw.rect(screen, (10,10,30), (offset_x, offset_y, GAME_WIDTH, HEIGHT))
        
        for hx, hy in holes_positions: 
            draw_hole(hx + offset_x, hy + offset_y)

        ret, frame = cap.read()
        hand_closed, hand_two, hand_one = False, False, False
        if ret:
            frame = cv2.flip(frame, 1)
            results = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if results.multi_hand_landmarks:
                lms = results.multi_hand_landmarks[0]
                hammer_x += (int(lms.landmark[8].x * GAME_WIDTH) - hammer_x) * 0.7
                hammer_y += (int(lms.landmark[8].y * HEIGHT) - hammer_y) * 0.7
                hand_history.append((int(hammer_x), int(hammer_y)))
                up = [lms.landmark[t].y < lms.landmark[t-2].y for t in [8, 12, 16, 20]]
                if sum(up) == 0: hand_closed, hand_status = True, "WHACK"
                elif up[0] and up[1] and sum(up) == 2: hand_two, hand_status = True, "FREEZE"
                elif up[0] and sum(up) == 1: hand_one, hand_status = True, "SLICE"
                else: hand_status = "MOVING"

        if hand_two and freeze_available and not slice_active:
            freeze_active, freeze_available, freeze_timer = True, False, 240
        if hand_one and slice_available and not freeze_active:
            slice_active, slice_available, slice_timer = True, False, 200

        mole_x, mole_y = holes_positions[mole_index]
        dist = math.hypot(hammer_x - mole_x, hammer_y - (mole_y - mole_y_offset))
        
        # --- Hit Logic ---
        if mole_up and hand_closed and dist < HAND_DISTANCE_THRESH and time.time() - last_whack_time > 0.3:
            shake_intensity, flash_alpha = 15, 60
            last_whack_time = time.time(); score += 1 + combo; combo += 1; combo_timer = time.time()
            hammer_target_angle, hit_anim_timer = -75, 12
            
            if settings['hardcore']:
                remaining_time += 1.0
                float_texts.append({'text': "+1s", 'x': mole_x + 40, 'y': mole_y-120, 'life': 40, 'col': (0, 255, 0)})
                if bonus_sound: bonus_sound.play()

            float_texts.append({'text': f"+{1+combo-1}", 'x': mole_x, 'y': mole_y-80, 'life': 30, 'col': (255,255,255)})
            if whack_sound: whack_sound.play()
            for _ in range(8): spark_particles.append({'x': mole_x, 'y': mole_y-30, 'vx': random.uniform(-4, 4), 'vy': random.uniform(-6, -1), 'life': 15, 'size': random.randint(2, 4)})
            if not freeze_active: mole_up = False 
        
        if mole_up and slice_active and dist < 85:
            shake_intensity, flash_alpha = 8, 40
            is_sliced = True; score += 3; combo += 1; combo_timer = time.time()
            
            if settings['hardcore']:
                remaining_time += 2.0
                float_texts.append({'text': "+2s", 'x': mole_x + 40, 'y': mole_y-120, 'life': 40, 'col': (0, 255, 255)})
                if bonus_sound: bonus_sound.play()

            float_texts.append({'text': "SLICE!", 'x': mole_x, 'y': mole_y-80, 'life': 30, 'col': (255, 0, 255)})
            if slice_sound: slice_sound.play()
            for _ in range(12): blood_particles.append({'x': mole_x, 'y': mole_y, 'vx': random.uniform(-6, 6), 'vy': random.uniform(-8, 2), 'life': 22, 'size': random.randint(3, 7)})
            if not freeze_active: mole_up = False

        mole_target_offset = 50 if mole_up else 0
        mole_y_offset += (mole_target_offset - mole_y_offset) * 0.4
        if hit_anim_timer > 0: hit_anim_timer -= 1
        else: hammer_target_angle = 0
        hammer_angle += (hammer_target_angle - hammer_angle) * 0.4

        if not freeze_active and (not mole_up or (time.time() - last_toggle > current_up_time)):
            mole_index = random.randint(0, len(holes_positions)-1)
            mole_up, is_sliced, last_toggle = True, False, time.time()

        pygame.draw.rect(screen, (20,20,50), (GAME_WIDTH, 0, CAM_WIDTH, HEIGHT))
        pygame.draw.rect(screen, (255,255,255), (GAME_WIDTH+10, 10, CAM_WIDTH-20, HEIGHT-20), 2, border_radius=10)

        draw_mole(mole_x + offset_x, (mole_y - mole_y_offset) + offset_y, is_sliced, hit_anim_timer > 0)
        draw_particles(blood_particles, (200, 0, 0))
        draw_particles(spark_particles, (255, 255, 100))
        draw_hammer_trail(hand_history, slice_active)
        draw_hammer(hammer_x, hammer_y, hammer_angle, slice_active)
        
        for ft in float_texts[:]:
            t_surf = small_font.render(ft['text'], True, ft.get('col', (255,255,255)))
            screen.blit(t_surf, (ft['x'] + offset_x, ft['y'] + offset_y))
            ft['y'] -= 2; ft['life'] -= 1
            if ft['life'] <= 0: float_texts.remove(ft)

        ind_col = (255, 50, 50) if hand_status == "WHACK" else (255, 0, 255) if hand_status == "SLICE" else (0, 255, 255)
        status_txt = small_font.render(f"[{hand_status}]", True, ind_col)
        screen.blit(status_txt, (hammer_x + 35, hammer_y - 35))

        # Side Panel HUD
        hx, hy = GAME_WIDTH + 60, 100
        combo_col = (255, 100, 255)
        if settings['hardcore'] and combo > 5:
            pulse = abs(math.sin(time.time()*15)) * 155
            combo_col = (255, pulse, 0)

        for i, (t, c) in enumerate([(f"SCORE: {score}", (0, 255, 100)), (f"HIGH: {max(score, current_highscore)}", (255, 200, 0)), (f"COMBO: x{combo}", combo_col)]):
            screen.blit(font.render(t, True, c), (hx, hy + i*80))
        
        if settings['hardcore']:
            speed_txt = small_font.render(f"INTENSITY: {int((1.5/current_up_time)*100)}%", True, (255, 50, 50))
            screen.blit(speed_txt, (hx, 340))
            # New Decay HUD
            decay_txt = small_font.render(f"TIME DECAY: x{time_speed:.2f}", True, (255, 100, 0))
            screen.blit(decay_txt, (hx, 370))

        # Skill Bars
        f_p = freeze_timer/240 if freeze_active else (MAX_SKILL_COOLDOWN - freeze_cd_timer)/MAX_SKILL_COOLDOWN
        s_p = slice_timer/180 if slice_active else (MAX_SLICE_COOLDOWN - slice_cd_timer)/MAX_SLICE_COOLDOWN
        
        screen.blit(small_font.render("FREEZE (2 FINGERS)", True, (0, 255, 255)), (hx, 445))
        pygame.draw.rect(screen, (40,40,70), (hx, 480, 400, 25), border_radius=10)
        pygame.draw.rect(screen, (0,255,255), (hx, 480, int(400*max(0, min(1, f_p))), 25), border_radius=10)
        
        screen.blit(small_font.render("BLADE STORM (1 FINGER)", True, (255, 0, 255)), (hx, 565))
        pygame.draw.rect(screen, (40,40,70), (hx, 600, 400, 25), border_radius=10)
        pygame.draw.rect(screen, (255,0,255), (hx, 600, int(400*max(0, min(1, s_p))), 25), border_radius=10)

        timer_col = (255, 50, 50) if remaining_time <= 5.9 else (255, 255, 255)
        timer_label = font.render("TIME REMAINING:", True, (150, 150, 150))
        timer_val = big_font.render(f"{max(0, current_sec)}s", True, timer_col)
        screen.blit(timer_label, (hx, 700))
        screen.blit(timer_val, (hx, 760))

        if 0 < remaining_time <= 5.0:
            pulse = abs(math.sin(time.time() * 10)) * 30
            count_surf = giant_font.render(str(current_sec), True, (255, 50 + pulse, 50))
            count_surf.set_alpha(150)
            screen.blit(count_surf, (GAME_WIDTH//2 - count_surf.get_width()//2, HEIGHT//2 - count_surf.get_height()//2))

        if freeze_active:
            freeze_timer -= 1
            if freeze_timer <= 0: freeze_active, freeze_cd_timer = False, MAX_SKILL_COOLDOWN
        elif freeze_cd_timer > 0:
            freeze_cd_timer -= 1
            if freeze_cd_timer <= 0: freeze_available = True

        if slice_active:
            slice_timer -= 1
            if slice_timer <= 0: slice_active, slice_cd_timer = False, MAX_SLICE_COOLDOWN
        elif slice_cd_timer > 0:
            slice_cd_timer -= 1
            if slice_cd_timer <= 0: slice_available = True

        if combo > 0 and time.time() - combo_timer > 2: combo = 0
        if remaining_time <= 0:
            game_over_screen(score, diff_name)
            return "back"
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); exit()
        
        pygame.display.update()
        clock.tick(60)

# ================= MAIN =================
while True:
    act = home_menu()
    if act == "start":
        df = difficulty_menu()
        if df: 
            while True:
                if game_loop(copy.deepcopy(DIFFICULTY[df]), df) == "back": break







