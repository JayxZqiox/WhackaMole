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

# --- Music Loader ---
def play_bg_music(state="menu"):
    try:
        if state == "menu":
            pygame.mixer.music.load(os.path.join(BASE_DIR, "menu_theme.mp3"))
            pygame.mixer.music.set_volume(0.4)
            pygame.mixer.music.play(-1)
        elif state == "game":
            pygame.mixer.music.load(os.path.join(BASE_DIR, "hardcore_theme.mp3"))
            pygame.mixer.music.set_volume(0.6)
            pygame.mixer.music.play(-1)
    except pygame.error as e:
        print(f"Audio Error: {e}")

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
click_sound = generate_beep(800, 0.05)

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
HAND_HISTORY_LEN = 20 # Increased for Motion Blur
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

def draw_hammer(x, y, angle=0, slice_active=False, is_clutch=False):
    if slice_active:
        col = (0, 255, 255) if is_clutch else (255, 0, 255)
        pygame.draw.line(screen, col, (x-45, y-45), (x+45, y+45), 14 if is_clutch else 12)
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

def draw_hammer_trail(trail_points, slice_active=False, is_clutch=False):
    points = list(trail_points)
    # Motion Blur: Show more points if clutch/slice is active
    trail_len = 20 if is_clutch else 12 if slice_active else 6
    for i, (x,y) in enumerate(points[-trail_len:]):
        alpha = int(255*(i/trail_len))
        color = (0, 255, 255) if is_clutch else (255, 0, 255) if slice_active else (255, 255, 255)
        # Blur effect: radius grows with speed/position in trail
        radius = 12 if is_clutch else 8 if slice_active else 5
        s = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
        pygame.draw.circle(s, color + (alpha,), (radius, radius), radius)
        screen.blit(s, (x-radius, y-radius))

# ================= MENUS =================
def game_over_screen(final_score, diff):
    high_score = save_highscore(diff, final_score)
    while True:
        draw_scrolling_background(pygame.time.get_ticks() // 10, diff=="hardcore")
        title = big_font.render("GAME OVER", True, (255, 50, 50))
        sc_txt = font.render(f"SCORE: {final_score}", True, (255, 255, 255))
        hs_txt = font.render(f"HIGH SCORE: {high_score}", True, (0, 255, 200))
        hint = small_font.render("Left Click anywhere to continue", True, (150, 150, 150))
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 250))
        screen.blit(sc_txt, (WIDTH//2 - sc_txt.get_width()//2, 400))
        screen.blit(hs_txt, (WIDTH//2 - hs_txt.get_width()//2, 480))
        screen.blit(hint, (WIDTH//2 - hint.get_width()//2, 650))
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); exit()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1: 
                click_sound.play()
                return
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
            elif event.type==pygame.MOUSEBUTTONDOWN and event.button == 1:
                if start_btn.collidepoint(event.pos): 
                    click_sound.play()
                    return "start"
                elif exit_btn.collidepoint(event.pos): 
                    pygame.quit(); exit()
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
            elif event.type==pygame.MOUSEBUTTONDOWN and event.button == 1:
                for rect, label, key in btns:
                    if rect.collidepoint(event.pos): 
                        click_sound.play()
                        return key
        pygame.display.update(); clock.tick(60)

# ================= GAME LOOP =================
def game_loop(settings, diff_name):
    play_bg_music("game")  
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
    float_texts = [] 

    freeze_available, freeze_active, freeze_timer, freeze_cd_timer = True, False, 0, 0
    slice_available, slice_active, slice_timer, slice_cd_timer = True, False, 0, 0
    hand_status, is_sliced = "MOVING", False

    while True:
        time_speed = 1.0
        if settings['hardcore']:
            time_speed = 1.0 + (score * 0.006) 
        
        if not freeze_active:
            remaining_time -= (1/60) * time_speed
            
        current_sec = int(math.ceil(remaining_time))
        current_up_time = settings['up_time']
        if settings['hardcore']:
            speed_penalty = score * 0.012
            current_up_time = max(0.25, settings['up_time'] - speed_penalty)

        if remaining_time <= 5.9 and current_sec != last_beep_time and current_sec >= 1:
            if warning_beep: warning_beep.play()
            last_beep_time = current_sec

        # --- Clutch Visual State ---
        is_clutch = slice_active and not settings['hardcore'] and remaining_time <= 5.0

        offset_x, offset_y = 0, 0
        if is_clutch: # Persistent shake for clutch
            shake_intensity = max(shake_intensity, 6) 
            
        if shake_intensity > 0:
            offset_x = random.randint(-shake_intensity, shake_intensity)
            offset_y = random.randint(-shake_intensity, shake_intensity)
            shake_intensity -= 1

        draw_scrolling_background(pygame.time.get_ticks() // 10, settings['hardcore'])
        pygame.draw.rect(screen, (10,10,30), (offset_x, offset_y, GAME_WIDTH, HEIGHT))
        
        for hx, hy in holes_positions: 
            draw_hole(hx + offset_x, hy + offset_y)

        # --- Hand Processing & Skills ---
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
                elif up[0] and up[1] and sum(up) == 2: 
                    hand_two, hand_status = True, "FREEZE"
                    if freeze_available:
                        freeze_active, freeze_available, freeze_timer = True, False, 240
                elif up[0] and sum(up) == 1: 
                    hand_one, hand_status = True, "SLICE"
                    if slice_available:
                        slice_active, slice_available = True, False
                        slice_timer = 350 if is_clutch else 200 # Extended for clutch
                else: hand_status = "MOVING"

        mole_x, mole_y = holes_positions[mole_index]
        dist = math.hypot(hammer_x - mole_x, hammer_y - (mole_y - mole_y_offset))
        
        # --- Hit Logic ---
        if mole_up and hand_closed and dist < HAND_DISTANCE_THRESH and time.time() - last_whack_time > 0.3:
            shake_intensity = 15
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
        
        # --- Slice Logic ---
        if mole_up and slice_active and dist < 85:
            shake_intensity = 8
            is_sliced = True; score += 3; combo += 1; combo_timer = time.time()
            
            if settings['hardcore']:
                remaining_time += 2.0
                float_texts.append({'text': "+2s", 'x': mole_x + 40, 'y': mole_y-120, 'life': 40, 'col': (0, 255, 255)})
            elif remaining_time <= 5.0:
                remaining_time += 0.5 # The +0.5s bonus
                float_texts.append({'text': "+0.5s", 'x': mole_x + 40, 'y': mole_y-120, 'life': 40, 'col': (0, 255, 255)})
            
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
        
        # Blur Trail & Hammer
        draw_hammer_trail(hand_history, slice_active, is_clutch)
        draw_hammer(hammer_x + offset_x, hammer_y + offset_y, hammer_angle, slice_active, is_clutch)
        
        for ft in float_texts[:]:
            t_surf = small_font.render(ft['text'], True, ft.get('col', (255,255,255)))
            screen.blit(t_surf, (ft['x'] + offset_x, ft['y'] + offset_y))
            ft['y'] -= 2; ft['life'] -= 1
            if ft['life'] <= 0: float_texts.remove(ft)

        # Status Label Logic
        if freeze_active and slice_active:
            label, ind_col = "[FROZEN BLADE!!]", (255, 255, 0)
        elif is_clutch:
            label, ind_col = "[CLUTCH SLICE!!]", (0, 255, 255)
        elif slice_active:
            label, ind_col = "[SLICE]", (255, 0, 255)
        elif freeze_active:
            label, ind_col = "[FREEZE]", (0, 255, 255)
        else:
            label, ind_col = f"[{hand_status}]", (255, 50, 50) if hand_status == "WHACK" else (255, 255, 255)

        status_txt = small_font.render(label, True, ind_col)
        screen.blit(status_txt, (hammer_x + 35 + offset_x, hammer_y - 35 + offset_y))

        hx, hy = GAME_WIDTH + 60, 100
        combo_col = (255, 100, 255)
        if settings['hardcore'] and combo > 5:
            pulse = abs(math.sin(time.time()*15)) * 155
            combo_col = (255, pulse, 0)

        for i, (t, c) in enumerate([(f"SCORE: {score}", (0, 255, 100)), (f"HIGH: {max(score, current_highscore)}", (255, 200, 0)), (f"COMBO: x{combo}", combo_col)]):
            screen.blit(font.render(t, True, c), (hx, hy + i*80))
        
        # Skill Bars
        f_p = freeze_timer/240 if freeze_active else (MAX_SKILL_COOLDOWN - freeze_cd_timer)/MAX_SKILL_COOLDOWN
        s_p = slice_timer/200 if slice_active else (MAX_SLICE_COOLDOWN - slice_cd_timer)/MAX_SLICE_COOLDOWN
        
        screen.blit(small_font.render("FREEZE (2 FINGERS)", True, (0, 255, 255)), (hx, 445))
        pygame.draw.rect(screen, (40,40,70), (hx, 480, 400, 25), border_radius=10)
        pygame.draw.rect(screen, (0,255,255), (hx, 480, int(400*max(0, min(1, f_p))), 25), border_radius=10)
        
        screen.blit(small_font.render("BLADE STORM (1 FINGER)", True, (255, 0, 255)), (hx, 565))
        pygame.draw.rect(screen, (40,40,70), (hx, 600, 400, 25), border_radius=10)
        pygame.draw.rect(screen, (255,0,255), (hx, 600, int(400*max(0, min(1, s_p))), 25), border_radius=10)

        timer_col = (255, 50, 50) if remaining_time <= 5.9 else (255, 255, 255)
        screen.blit(font.render("TIME REMAINING:", True, (150, 150, 150)), (hx, 700))
        screen.blit(big_font.render(f"{max(0, current_sec)}s", True, timer_col), (hx, 760))

        if 0 < remaining_time <= 5.0:
            pulse = abs(math.sin(time.time() * 10)) * 30
            count_surf = giant_font.render(str(current_sec), True, (255, 50 + pulse, 50))
            count_surf.set_alpha(150)
            screen.blit(count_surf, (GAME_WIDTH//2 - count_surf.get_width()//2, HEIGHT//2 - count_surf.get_height()//2))

        # Skill Timers
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
            pygame.mixer.music.fadeout(1000) 
            game_over_screen(score, diff_name)
            return "back"
            
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); exit()
        
        pygame.display.update()
        clock.tick(60)

# ================= MAIN =================
while True:
    play_bg_music("menu")   
    act = home_menu()
    if act == "start":
        df = difficulty_menu()
        if df: 
            while True:
                if game_loop(copy.deepcopy(DIFFICULTY[df]), df) == "back": 
                    pygame.mixer.music.set_volume(0.4)
                    break   