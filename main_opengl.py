import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import math
import random
import sys
import os
import json

# --- Settings ---
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768
NORMAL_SPEED = 0.07
RUN_SPEED = 0.15

# --- Maze Generation (Procedural/Random) ---
def generate_maze(width, height):
    if width % 2 == 0: width += 1
    if height % 2 == 0: height += 1
    maze = [[1 for _ in range(width)] for _ in range(height)]
    stack = [(1, 1)]
    maze[1][1] = 0
    while stack:
        x, y = stack[-1]
        dirs = [(0, 2), (0, -2), (2, 0), (-2, 0)]
        random.shuffle(dirs)
        found = False
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height and maze[ny][nx] == 1:
                maze[y + dy // 2][x + dx // 2] = 0
                maze[ny][nx] = 0
                stack.append((nx, ny))
                found = True
                break
        if not found: stack.pop()
    maze[1][0] = 0 
    maze[height-2][width-1] = 0 
    return maze

# --- OpenGL Drawing Helpers ---
def draw_cube(x, y, z, size=1.0, wall_color=(0, 0.4, 0.4), edge_color=(0, 1, 1)):
    v = size / 2.0
    glBegin(GL_QUADS)
    glColor3fv(wall_color)
    glVertex3f(x-v, y-v, z+v); glVertex3f(x+v, y-v, z+v); glVertex3f(x+v, y+v, z+v); glVertex3f(x-v, y+v, z+v)
    glVertex3f(x-v, y-v, z-v); glVertex3f(x-v, y+v, z-v); glVertex3f(x+v, y+v, z-v); glVertex3f(x+v, y-v, z-v)
    glVertex3f(x-v, y+v, z-v); glVertex3f(x-v, y+v, z+v); glVertex3f(x+v, y+v, z+v); glVertex3f(x+v, y+v, z-v)
    glVertex3f(x-v, y-v, z-v); glVertex3f(x+v, y-v, z-v); glVertex3f(x+v, y-v, z+v); glVertex3f(x-v, y-v, z+v)
    glVertex3f(x+v, y-v, z-v); glVertex3f(x+v, y+v, z-v); glVertex3f(x+v, y+v, z+v); glVertex3f(x+v, y-v, z+v)
    glVertex3f(x-v, y-v, z-v); glVertex3f(x-v, y-v, z+v); glVertex3f(x-v, y+v, z+v); glVertex3f(x-v, y+v, z-v)
    glEnd()

    glLineWidth(2)
    glBegin(GL_LINES)
    glColor3fv(edge_color)
    glVertex3f(x-v, y-v, z-v); glVertex3f(x+v, y-v, z-v)
    glVertex3f(x+v, y-v, z-v); glVertex3f(x+v, y-v, z+v)
    glVertex3f(x+v, y-v, z+v); glVertex3f(x-v, y-v, z+v)
    glVertex3f(x-v, y-v, z+v); glVertex3f(x-v, y-v, z-v)
    glVertex3f(x-v, y+v, z-v); glVertex3f(x+v, y+v, z-v)
    glVertex3f(x+v, y+v, z-v); glVertex3f(x+v, y+v, z+v)
    glVertex3f(x+v, y+v, z+v); glVertex3f(x-v, y+v, z+v)
    glVertex3f(x-v, y+v, z+v); glVertex3f(x-v, y+v, z-v)
    glVertex3f(x-v, y-v, z-v); glVertex3f(x-v, y+v, z-v)
    glVertex3f(x+v, y-v, z-v); glVertex3f(x+v, y+v, z-v)
    glVertex3f(x+v, y-v, z+v); glVertex3f(x+v, y+v, z+v)
    glVertex3f(x-v, y-v, z+v); glVertex3f(x-v, y+v, z+v)
    glEnd()

class Game:
    def __init__(self):
        pygame.init()
        # Initialize display with OpenGL and RESIZABLE
        self.width = SCREEN_WIDTH
        self.height = SCREEN_HEIGHT
        self.screen = pygame.display.set_mode((self.width, self.height), DOUBLEBUF | OPENGL | RESIZABLE)
        pygame.display.set_caption("Laze - OpenGL Edition")
        self.clock = pygame.time.Clock()
        
        self.camera_pos = [1.5, 0.5, 1.5]
        self.camera_rot = [0, 0] # [Yaw, Pitch]
        self.previous_state = "MENU"
        
        # --- Settings Variables ---
        self.settings_file = "settings.json"
        self.volume = 0.3
        self.sensitivity = 0.1
        self.fov = 60
        self.load_settings()
        
        # --- Physics / Jumping ---
        self.velocity_y = 0.0
        self.gravity = 0.005
        self.jump_force = 0.12
        self.is_jumping = False
        self.ground_level = 0.5 # Camera eye level when standing
        
        # --- Audio Initialization ---
        self.music_files = []
        self.current_track = None
        self.init_audio()
            
        self.maze_size = 11
        self.maze_data = []
        self.maze_list = None 
        
        self.state = "MENU"
        self.menu_options = ["Start Game", "Settings", "Exit"]
        self.selected_option = 0
        
        # Settings Menu options
        self.settings_options = ["Volume", "Sensitivity", "Back"]
        self.selected_setting = 0
        
        self.font = pygame.font.SysFont('Arial', 32)
        self.small_font = pygame.font.SysFont('Arial', 24)
        
        self.stars = []
        self.init_stars()
        
        # Initial Level Generation for Menu Background
        self.generate_level()

    def draw_text_opengl(self, text, x, y, color=(1.0, 1.0, 1.0), font=None):
        if font is None: font = self.font
        # Render text in WHITE onto texture
        text_surface = font.render(text, True, (255, 255, 255, 255))
        text_data = pygame.image.tostring(text_surface, "RGBA", True)
        width, height = text_surface.get_width(), text_surface.get_height()
        
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, text_data)
        
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        
        # Tint the white text with the desired color
        glColor3f(color[0], color[1], color[2])
        
        glBegin(GL_QUADS)
        # Flip texture vertically by swapping V coordinates
        glTexCoord2f(0, 1); glVertex2f(x, y)
        glTexCoord2f(1, 1); glVertex2f(x + width, y)
        glTexCoord2f(1, 0); glVertex2f(x + width, y + height)
        glTexCoord2f(0, 0); glVertex2f(x, y + height)
        glEnd()
        
        glDisable(GL_TEXTURE_2D)
        glDeleteTextures([tex_id])
        glDisable(GL_BLEND)

    def setup_2d_ortho(self):
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluOrtho2D(0, SCREEN_WIDTH, SCREEN_HEIGHT, 0) 
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_FOG)
        glDisable(GL_LIGHTING)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA) 

    def restore_3d_projection(self):
        # We don't need to pop matrices because we rebuild them every frame in setup_3d
        # Just re-enable 3D states
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_FOG)
        glDisable(GL_BLEND)

    def draw_text_centered(self, text, y_pos, color=(0.0, 1.0, 0.0), selected=False, font=None):
        if selected:
            color = (0.0, 1.0, 1.0) # Cyan for selected
        
        if font is None: font = self.font
        
        # Calculate X based on size, but we need the surface size.
        # We render a dummy surface just to get width (or cache it, but this is fine for menu)
        # Actually render logic is inside draw_text_opengl but we need x position.
        # Optimization: Don't render twice.
        # But draw_text_opengl generates texture.
        # Let's verify width here.
        sz = font.size(text)
        x_pos = SCREEN_WIDTH//2 - sz[0]//2
        
        self.draw_text_opengl(text, x_pos, y_pos, color, font)

    def render_scene(self):
        # Setup 3D Projection
        self.setup_3d()
        
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        
        glRotatef(self.camera_rot[1], 1, 0, 0)
        glRotatef(self.camera_rot[0], 0, 1, 0)
        
        self.draw_retro_sky()
        
        glTranslatef(-self.camera_pos[0], -self.camera_pos[1], -self.camera_pos[2])
        glCallList(self.maze_list)
        
        # Exit Cube
        glColor3f(0, 1, 1)
        draw_cube(self.maze_size-1, 0.5, self.maze_size-2, 0.6, wall_color=(0, 1, 1), edge_color=(1, 1, 1))

    def init_stars(self):
        for _ in range(200):
            # Stars in the upper hemisphere
            theta = random.uniform(0, 2 * math.pi)
            phi = random.uniform(0, math.pi / 2.2) # Closer to horizon
            r = 100.0 # Further away
            
            x = r * math.sin(phi) * math.cos(theta)
            y = r * math.cos(phi)
            z = r * math.sin(phi) * math.sin(theta)
            self.stars.append((x, y, z))
        
    def init_audio(self):
        try:
            pygame.mixer.init()
            # Find all audio files in 'music' folder
            music_dir = 'music'
            if os.path.exists(music_dir) and os.path.isdir(music_dir):
                exts = ('.mp3', '.ogg', '.wav')
                for file in os.listdir(music_dir):
                    if file.lower().endswith(exts):
                        self.music_files.append(os.path.join(music_dir, file))
            
            if self.music_files:
                self.play_random_music()
            else:
                print("No music files found in 'music' folder.")
        except Exception as e:
            print(f"Audio init error: {e}")

    def play_random_music(self):
        if not self.music_files: return
        track = random.choice(self.music_files)
        print(f"Playing: {track}")
        try:
            pygame.mixer.music.load(track)
            pygame.mixer.music.set_volume(self.volume)
            pygame.mixer.music.set_endevent(USEREVENT)
            pygame.mixer.music.play(0) 
        except Exception as e:
            print(f"Error playing {track}: {e}")

    def setup_3d(self):
        # Update Viewport
        glViewport(0, 0, self.width, self.height)
        
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_FOG)
        # Retro Synthwave Background and Fog
        bg_color = (0.1, 0.0, 0.2, 1.0) # Dark Purple
        glClearColor(*bg_color)
        glFogfv(GL_FOG_COLOR, bg_color)
        glFogf(GL_FOG_DENSITY, 0.05) # Less dense to see the sky
        glHint(GL_FOG_HINT, GL_NICEST)
        
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        if self.height == 0: self.height = 1 # Prevent div by zero
        gluPerspective(self.fov, (self.width / self.height), 0.1, 150.0) # Increase draw distance
        glMatrixMode(GL_MODELVIEW)

    def draw_retro_sky(self):
        # Save state
        glPushAttrib(GL_ENABLE_BIT)
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_FOG)
        glDisable(GL_LIGHTING)
        
        glPushMatrix()
        glTranslatef(self.camera_pos[0], self.camera_pos[1], self.camera_pos[2])
        
        size = 80.0
        height = 60.0 # Higher Sky
        
        # --- Gradient Sky Background ---
        glBegin(GL_QUADS)
        
        # Colors - Deep Space (Almost Black) to Retro Purple/Pink at Horizon
        top_color = (0.02, 0.0, 0.05)     # Deep Void
        mid_color = (0.2, 0.0, 0.3)      # Mid Purple
        horizon_color = (0.6, 0.1, 0.4)  # Magenta Horizon
        
        # We'll draw sides with vertical gradient
        # Front
        glColor3fv(horizon_color); glVertex3f(-size, -20, -size)
        glColor3fv(horizon_color); glVertex3f(size, -20, -size)
        glColor3fv(top_color);     glVertex3f(size, height, -size)
        glColor3fv(top_color);     glVertex3f(-size, height, -size)
        
        # Back
        glColor3fv(horizon_color); glVertex3f(size, -20, size)
        glColor3fv(horizon_color); glVertex3f(-size, -20, size)
        glColor3fv(top_color);     glVertex3f(-size, height, size)
        glColor3fv(top_color);     glVertex3f(size, height, size)
        
        # Left
        glColor3fv(horizon_color); glVertex3f(-size, -20, size)
        glColor3fv(horizon_color); glVertex3f(-size, -20, -size)
        glColor3fv(top_color);     glVertex3f(-size, height, -size)
        glColor3fv(top_color);     glVertex3f(-size, height, size)
        
        # Right
        glColor3fv(horizon_color); glVertex3f(size, -20, -size)
        glColor3fv(horizon_color); glVertex3f(size, -20, size)
        glColor3fv(top_color);     glVertex3f(size, height, size)
        glColor3fv(top_color);     glVertex3f(size, height, -size)
        
        # Top Lid
        glColor3fv(top_color)
        glVertex3f(-size, height, -size); glVertex3f(size, height, -size)
        glVertex3f(size, height, size); glVertex3f(-size, height, size)
        
        glEnd()
        
        # --- Stars ---
        glPointSize(2)
        glBegin(GL_POINTS)
        glColor3f(1, 1, 1)
        for s in self.stars:
            glVertex3f(s[0], s[1], s[2])
        glEnd()
        
        # --- Retro Sun ---
        # Draw a sun on the horizon (North / -Z direction)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE) 
        
        glPushMatrix()
        glTranslatef(0, 0, -30) # Distance
        
        # Sun Body (Circle)
        segments = 32
        radius = 8.0
        glBegin(GL_TRIANGLE_FAN)
        glColor4f(1.0, 0.9, 0.2, 0.9) # Center Bright Yellow
        glVertex3f(0, 3, 0)
        
        glColor4f(1.0, 0.1, 0.6, 0.4) # Rim Pink/Red
        for i in range(segments + 1):
            theta = 2.0 * math.pi * i / segments
            dx = radius * math.cos(theta)
            dy = radius * math.sin(theta) + 3 # Shift up slightly
            glVertex3f(dx, dy, 0)
        glEnd()
        
        glPopMatrix()
        
        glDisable(GL_BLEND)
        glPopMatrix()
        glPopAttrib()

    def generate_level(self):
        self.maze_data = generate_maze(self.maze_size, self.maze_size)
        if self.maze_list:
            glDeleteLists(self.maze_list, 1)
        self.maze_list = glGenLists(1)
        glNewList(self.maze_list, GL_COMPILE)
        
        # Floor
        glBegin(GL_QUADS)
        glColor3f(0.05, 0.05, 0.1)
        glVertex3f(-1, -0.5, -1); glVertex3f(self.maze_size, -0.5, -1)
        glVertex3f(self.maze_size, -0.5, self.maze_size); glVertex3f(-1, -0.5, self.maze_size)
        glEnd()
        
        # Floor Grid
        glBegin(GL_LINES)
        glColor3f(0, 0.3, 0.5)
        for i in range(-1, self.maze_size + 1):
            glVertex3f(i, -0.49, -1); glVertex3f(i, -0.49, self.maze_size)
            glVertex3f(-1, -0.49, i); glVertex3f(self.maze_size, -0.49, i)
        glEnd()
        
        # Ceiling - REMOVED for open sky
        # glColor3f(0, 0, 0)
        # glBegin(GL_QUADS)
        # glVertex3f(-1, 2.0, -1); glVertex3f(self.maze_size, 2.0, -1)
        # glVertex3f(self.maze_size, 2.0, self.maze_size); glVertex3f(-1, 2.0, self.maze_size)
        # glEnd()

        # Walls
        for y, row in enumerate(self.maze_data):
            for x, cell in enumerate(row):
                if cell == 1:
                    draw_cube(x, 0.5, y, 1.0, wall_color=(0, 0.05, 0.15), edge_color=(0, 0.8, 1))
        
        # Perimeter
        for x in range(-1, self.maze_size + 1):
            draw_cube(x, 0.5, -1, wall_color=(0.1, 0.1, 0.2), edge_color=(0.4, 0.4, 0.8))
            draw_cube(x, 0.5, self.maze_size, wall_color=(0.1, 0.1, 0.2), edge_color=(0.4, 0.4, 0.8))
        for y in range(-1, self.maze_size + 1):
            draw_cube(-1, 0.5, y, wall_color=(0.1, 0.1, 0.2), edge_color=(0.4, 0.4, 0.8))
            draw_cube(self.maze_size, 0.5, y, wall_color=(0.1, 0.1, 0.2), edge_color=(0.4, 0.4, 0.8))
            
        glEndList()
        self.camera_pos = [1.5, 0.5, 1.5]



    def render_scene(self):
        self.setup_3d() # Restore 3D projection
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        
        glRotatef(self.camera_rot[1], 1, 0, 0)
        glRotatef(self.camera_rot[0], 0, 1, 0)
        glTranslatef(-self.camera_pos[0], -self.camera_pos[1], -self.camera_pos[2])
        
        self.draw_retro_sky()
        glCallList(self.maze_list)
        
        # Exit Cube
        glColor3f(0, 1, 1)
        draw_cube(self.maze_size-1, 0.5, self.maze_size-2, 0.6, wall_color=(0, 1, 1), edge_color=(1, 1, 1))

    def handle_menu(self):
        # Don't switch set_mode, keep OpenGL
        running = True
        while running:
            # Render Background
            self.render_scene()
            
            # Overlay 2D Menu
            self.setup_2d_ortho()
            
            title_text = "LAZE - OPENGL"
            self.draw_text_centered(title_text, 100, (0.0, 1.0, 1.0))
            
            start_y = 300
            for i, option in enumerate(self.menu_options):
                self.draw_text_centered(option, start_y + i * 60, selected=(i == self.selected_option))
            
            self.restore_3d_projection() # Restore 3D projection before flipping
            pygame.display.flip()
            
            self.clock.tick(60)

            for event in pygame.event.get():
                if event.type == QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == VIDEORESIZE:
                    self.width, self.height = event.w, event.h
                    glViewport(0, 0, self.width, self.height)
                if event.type == USEREVENT:
                    self.play_random_music()
                if event.type == KEYDOWN:
                    if event.key == K_UP:
                        self.selected_option = (self.selected_option - 1) % len(self.menu_options)
                    elif event.key == K_DOWN:
                        self.selected_option = (self.selected_option + 1) % len(self.menu_options)
                    elif event.key == K_RETURN or event.key == K_SPACE:
                        if self.selected_option == 0: # Start
                            self.state = "GAME"
                            # If coming from fresh start, maybe regen? 
                            # But user said "walls don't disappear", implying continuity.
                            # So we keep current state unless we want a NEW game.
                            # Usually "Start Game" means New Game if from main menu?
                            # Let's check if we have moved. If camera is at default, fine.
                            # Let's just enter GAME state. If player wants new game, they might need a function for that.
                            # For now, let's just Resume/Enter.
                            pygame.mouse.set_visible(False)
                            pygame.event.set_grab(True)
                            return
                        elif self.selected_option == 1: # Settings
                            self.previous_state = "MENU"
                            self.state = "SETTINGS"
                            return
                        elif self.selected_option == 2: # Exit
                            pygame.quit()
                            sys.exit()

    def handle_settings(self):
        running = True
        while running:
            self.render_scene()
            self.setup_2d_ortho()
            
            self.draw_text_centered("SETTINGS", 100, (0.0, 1.0, 1.0))
            
            vol_str = f"Volume: {int(self.volume * 100)}%"
            self.draw_text_centered(vol_str, 300, selected=(self.selected_setting == 0))
            
            sens_str = f"Sensitivity: {self.sensitivity:.2f}"
            self.draw_text_centered(sens_str, 360, selected=(self.selected_setting == 1))
            
            self.draw_text_centered("Back", 420, selected=(self.selected_setting == 2))
            
            self.draw_text_centered("Use LEFT/RIGHT to adjust, ENTER to select", 600, (0.4, 0.4, 0.4), font=self.small_font)
            
            self.restore_3d_projection() # Restore 3D projection before flipping
            pygame.display.flip()
            self.clock.tick(60)
            
            for event in pygame.event.get():
                if event.type == QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == VIDEORESIZE:
                    self.width, self.height = event.w, event.h
                    glViewport(0, 0, self.width, self.height)
                if event.type == USEREVENT:
                    self.play_random_music()
                if event.type == KEYDOWN:
                    if event.key == K_UP:
                        self.selected_setting = (self.selected_setting - 1) % len(self.settings_options)
                    elif event.key == K_DOWN:
                        self.selected_setting = (self.selected_setting + 1) % len(self.settings_options)
                    elif event.key == K_LEFT:
                        if self.selected_setting == 0: # Volume
                            self.volume = max(0.0, self.volume - 0.1)
                            pygame.mixer.music.set_volume(self.volume)
                        elif self.selected_setting == 1: # Sensitivity
                            self.sensitivity = max(0.01, self.sensitivity - 0.01)
                    elif event.key == K_RIGHT:
                        if self.selected_setting == 0: # Volume
                            self.volume = min(1.0, self.volume + 0.1)
                            pygame.mixer.music.set_volume(self.volume)
                        elif self.selected_setting == 1: # Sensitivity
                            self.sensitivity = min(0.5, self.sensitivity + 0.01)
                    elif event.key == K_RETURN or event.key == K_SPACE or event.key == K_ESCAPE:
                        if self.selected_setting == 2 or event.key == K_ESCAPE: # Back
                            self.save_settings()
                            self.state = self.previous_state
                            return

    def handle_pause(self):
        running = True
        while running:
            self.render_scene()
            self.setup_2d_ortho()
            
            self.draw_text_centered("PAUSED", 100, (0, 255, 255))
            
            options = ["Resume", "Settings", "Main Menu"]
            start_y = 300
            for i, option in enumerate(options):
                self.draw_text_centered(option, start_y + i * 60, selected=(i == self.selected_option))
            
            self.restore_3d_projection()
            pygame.display.flip()
            self.clock.tick(60)
            
            for event in pygame.event.get():
                if event.type == QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == VIDEORESIZE:
                    self.width, self.height = event.w, event.h
                    glViewport(0, 0, self.width, self.height)
                if event.type == USEREVENT:
                    self.play_random_music()
                if event.type == KEYDOWN:
                    if event.key == K_UP:
                        self.selected_option = (self.selected_option - 1) % len(options)
                    elif event.key == K_DOWN:
                        self.selected_option = (self.selected_option + 1) % len(options)
                    elif event.key == K_RETURN or event.key == K_SPACE:
                        if self.selected_option == 0: # Resume
                            self.state = "GAME"
                            pygame.mouse.set_visible(False)
                            pygame.event.set_grab(True)
                            return
                        elif self.selected_option == 1: # Settings
                            self.previous_state = "PAUSED"
                            self.state = "SETTINGS"
                            return
                        elif self.selected_option == 2: # Main Menu
                            self.state = "MENU"
                            self.save_settings()
                            return
                    elif event.key == K_ESCAPE:
                        self.state = "GAME"
                        pygame.mouse.set_visible(False)
                        pygame.event.set_grab(True)
                        return

    def draw_minimap(self):
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, self.width, self.height, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_FOG)
        
        # Draw background
        size = 200
        padding = 20
        mx, my = self.width - size - padding, padding
        
        glColor4f(0, 0, 0, 0.8)
        glBegin(GL_QUADS)
        glVertex2f(mx, my); glVertex2f(mx+size, my)
        glVertex2f(mx+size, my+size); glVertex2f(mx, my+size)
        glEnd()
        
        # Draw maze cells
        cell_size = size / self.maze_size
        for y in range(self.maze_size):
            for x in range(self.maze_size):
                if self.maze_data[y][x] == 1:
                    glColor3f(0.3, 0.3, 0.3)
                    glBegin(GL_QUADS)
                    glVertex2f(mx + x*cell_size, my + y*cell_size)
                    glVertex2f(mx + (x+1)*cell_size, my + y*cell_size)
                    glVertex2f(mx + (x+1)*cell_size, my + (y+1)*cell_size)
                    glVertex2f(mx + x*cell_size, my + (y+1)*cell_size)
                    glEnd()
        
        # Exit dot
        glColor3f(0, 1, 1)
        ex, ey = self.maze_size-1, self.maze_size-2
        glBegin(GL_QUADS)
        glVertex2f(mx + ex*cell_size, my + ey*cell_size)
        glVertex2f(mx + (ex+1)*cell_size, my + ey*cell_size)
        glVertex2f(mx + (ex+1)*cell_size, my + (ey+1)*cell_size)
        glVertex2f(mx + ex*cell_size, my + (ey+1)*cell_size)
        glEnd()

        # Player dot
        glColor3f(1, 0, 0)
        px, pz = self.camera_pos[0], self.camera_pos[2]
        glPointSize(5)
        glBegin(GL_POINTS)
        glVertex2f(mx + px*cell_size, my + pz*cell_size)
        glEnd()
        
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_FOG)
        
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()

    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    data = json.load(f)
                    self.volume = data.get("volume", 0.3)
                    self.sensitivity = data.get("sensitivity", 0.1)
                    print("Settings loaded.")
        except Exception as e:
            print(f"Failed to load settings: {e}")

    def save_settings(self):
        try:
            data = {
                "volume": self.volume,
                "sensitivity": self.sensitivity
            }
            with open(self.settings_file, 'w') as f:
                json.dump(data, f)
            print("Settings saved.")
        except Exception as e:
            print(f"Failed to save settings: {e}")

    def run(self):
        while True:
            if self.state == "MENU":
                self.handle_menu()
            elif self.state == "SETTINGS":
                self.handle_settings()
            elif self.state == "PAUSED":
                self.handle_pause()
            elif self.state == "GAME":
                dt = self.clock.tick(60) / 1000.0
                
                for event in pygame.event.get():
                    if event.type == QUIT:
                        pygame.quit()
                        sys.exit()
                    if event.type == VIDEORESIZE:
                        self.width, self.height = event.w, event.h
                        glViewport(0, 0, self.width, self.height)
                    if event.type == USEREVENT:
                        self.play_random_music()
                    if event.type == KEYDOWN:
                        if event.key == K_ESCAPE:
                            self.state = "PAUSED"
                            self.selected_option = 0
                            pygame.mouse.set_visible(True)
                            pygame.event.set_grab(False)
                        if event.key == K_SPACE and not self.is_jumping:
                            self.velocity_y = self.jump_force
                            self.is_jumping = True

                self.velocity_y -= self.gravity
                self.camera_pos[1] += self.velocity_y
                
                if self.camera_pos[1] <= self.ground_level:
                    self.camera_pos[1] = self.ground_level
                    self.velocity_y = 0
                    self.is_jumping = False

                mx, my = pygame.mouse.get_rel()
                self.camera_rot[0] += mx * self.sensitivity
                self.camera_rot[1] += my * self.sensitivity
                self.camera_rot[1] = max(-80, min(80, self.camera_rot[1]))
                
                keys = pygame.key.get_pressed()
                current_speed = RUN_SPEED if keys[K_LSHIFT] or keys[K_RSHIFT] else NORMAL_SPEED
                
                move_vec = [0, 0]
                if keys[K_w]: move_vec[1] += 1
                if keys[K_s]: move_vec[1] -= 1
                if keys[K_a]: move_vec[0] -= 1
                if keys[K_d]: move_vec[0] += 1
                
                if move_vec != [0, 0]:
                    yaw_rad = math.radians(self.camera_rot[0])
                    forward_x = math.sin(yaw_rad)
                    forward_z = -math.cos(yaw_rad)
                    side_x = math.cos(yaw_rad)
                    side_z = math.sin(yaw_rad)
                    
                    dx = (move_vec[1] * forward_x + move_vec[0] * side_x) * current_speed
                    dz = (move_vec[1] * forward_z + move_vec[0] * side_z) * current_speed
                    
                    # --- Collision ---
                    buff = 0.3 
                    def is_walkable(nx, nz):
                        if nx < -0.5 or nz < -0.5 or nx > self.maze_size - 0.5 or nz > self.maze_size - 0.5:
                            return False
                        grid_x = int(round(nx))
                        grid_z = int(round(nz))
                        if 0 <= grid_x < self.maze_size and 0 <= grid_z < self.maze_size:
                            if self.maze_data[grid_z][grid_x] == 1:
                                return False
                        return True

                    if is_walkable(self.camera_pos[0] + dx + (buff if dx > 0 else -buff), self.camera_pos[2]):
                        self.camera_pos[0] += dx
                    
                    if is_walkable(self.camera_pos[0], self.camera_pos[2] + dz + (buff if dz > 0 else -buff)):
                        self.camera_pos[2] += dz

                dist_to_exit = math.sqrt((self.camera_pos[0] - (self.maze_size-1))**2 + (self.camera_pos[2] - (self.maze_size-2))**2)
                if dist_to_exit < 1.0:
                    self.maze_size += 4
                    self.generate_level()

                self.render_scene()
                
                # Mini-map
                if keys[K_TAB]:
                    self.draw_minimap()
                    
                pygame.display.flip()

if __name__ == "__main__":
    game = Game()
    game.run()
