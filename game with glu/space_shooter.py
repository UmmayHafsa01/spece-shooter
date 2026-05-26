"""
Retro 2D Space Shooter Game in PyOpenGL
========================================

A complete 2D Space Shooter game built using PyOpenGL (OpenGL.GL, OpenGL.GLU, and OpenGL.GLUT).
Features:
- Responsive, smooth player spaceship controls using Arrow keys.
- Laser firing system using the Spacebar.
- Falling enemy grids (rectangles) and asteroids (circles) with dynamic difficulty scaling.
- Custom particle explosions on destroying enemies.
- Live score and high score display using GLUT bitmap fonts.
- Background scrolling starfield.
- Semi-transparent game over screen overlay with restart functionality ('R' key).

Requirements:
- Python 3.x
- PyOpenGL (install via: pip install PyOpenGL PyOpenGL_accelerate)

Author: Antigravity AI
"""

import sys
import math
import random
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *

# ==========================================
# GAME CLASS DEFINITION
# ==========================================

class SpaceShooterGame:
    def __init__(self):
        # Window attributes
        self.width = 800
        self.height = 600
        
        # Player attributes
        self.player_x = 400.0
        self.player_y = 60.0
        self.player_w = 40.0 # Width of the ship body
        self.player_h = 40.0 # Height of the ship body
        self.player_speed = 7.0
        
        # Game entities
        self.bullets = []       # Active lasers: list of {'x', 'y', 'w', 'h', 'speed'}
        self.enemies = []       # Active hazards: list of {'x', 'y', 'w', 'h', 'speed', 'color', 'type', 'radius'}
        self.stars = []         # Background star coordinates: list of {'x', 'y', 'speed', 'color', 'size'}
        self.explosions = []    # Particle visual effects: list of {'x', 'y', 'vx', 'vy', 'life', 'decay', 'color'}
        
        # Key states for smooth movement (avoids OS keyboard-repeat delay)
        self.keys = {
            'left': False,
            'right': False,
            'up': False,
            'down': False,
            'space': False
        }
        
        # Game stats & logic
        self.score = 0
        self.high_score = 0
        self.game_over = False
        
        # Timers
        self.shoot_cooldown = 0
        self.spawn_timer = 0
        self.survival_timer = 0 # To increment score slowly over time
        
        # Initialization
        self.init_stars()

    def reset_game(self):
        """Resets the game state to default for a new run."""
        self.player_x = 400.0
        self.player_y = 60.0
        self.bullets.clear()
        self.enemies.clear()
        self.explosions.clear()
        for k in self.keys:
            self.keys[k] = False
        self.score = 0
        self.game_over = False
        self.shoot_cooldown = 0
        self.spawn_timer = 0
        self.survival_timer = 0

    # ------------------------------------------
    # BACKGROUND STARFIELD INITIALIZATION
    # ------------------------------------------
    def init_stars(self):
        """Initializes random stars at different depths (speeds)."""
        self.stars = []
        for _ in range(100):
            self.stars.append({
                'x': random.uniform(0, self.width),
                'y': random.uniform(0, self.height),
                'speed': random.uniform(1.0, 4.0),
                'color': random.uniform(0.4, 1.0), # Star brightness
                'size': random.uniform(1.0, 3.0)
            })

    def update_stars(self):
        """Scrolls stars downwards to simulate forward motion in space."""
        for star in self.stars:
            star['y'] -= star['speed']
            # If a star passes the bottom of the screen, spawn it back at the top
            if star['y'] < 0:
                star['y'] = self.height
                star['x'] = random.uniform(0, self.width)
                star['speed'] = random.uniform(1.0, 4.0)
                star['color'] = random.uniform(0.4, 1.0)
                star['size'] = random.uniform(1.0, 3.0)

    # ------------------------------------------
    # PARTICLE EXPLOSIONS
    # ------------------------------------------
    def spawn_explosion(self, x, y, color):
        """Spawns radial particles at the location of destruction."""
        for _ in range(15):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(2.0, 6.0)
            self.explosions.append({
                'x': x,
                'y': y,
                'vx': math.cos(angle) * speed,
                'vy': math.sin(angle) * speed,
                'life': 1.0, # Opacity/life percentage (starts at 100%)
                'decay': random.uniform(0.03, 0.06), # Fade rate
                'color': color
            })

    def update_explosions(self):
        """Moves particles and decays their lifetime."""
        for p in self.explosions[:]:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['life'] -= p['decay']
            if p['life'] <= 0:
                self.explosions.remove(p)

    # ------------------------------------------
    # ENEMY SPAWNING AND MOVING
    # ------------------------------------------
    def spawn_enemy(self):
        """Spawns an enemy block or asteroid at the top of the screen."""
        enemy_type = random.choice(['block', 'asteroid'])
        
        # Scale speed and spacing slowly based on the score to make it harder
        difficulty_speed_bonus = self.score / 200.0
        base_speed = random.uniform(2.0, 4.0) + difficulty_speed_bonus
        
        x_pos = random.uniform(40, self.width - 40)
        y_pos = self.height + 40
        
        if enemy_type == 'block':
            # Block parameters
            w = random.uniform(30.0, 50.0)
            h = random.uniform(30.0, 50.0)
            color = (random.uniform(0.7, 1.0), random.uniform(0.1, 0.3), random.uniform(0.6, 1.0)) # Vibrant purple/magenta
            self.enemies.append({
                'type': 'block',
                'x': x_pos,
                'y': y_pos,
                'w': w,
                'h': h,
                'speed': base_speed,
                'color': color,
                'radius': max(w, h) / 2.0
            })
        else:
            # Asteroid parameters
            radius = random.uniform(15.0, 25.0)
            color = (random.uniform(0.5, 0.7), random.uniform(0.4, 0.6), random.uniform(0.4, 0.5)) # Gray/Brown rocky color
            self.enemies.append({
                'type': 'asteroid',
                'x': x_pos,
                'y': y_pos,
                'w': radius * 2.0,
                'h': radius * 2.0,
                'speed': base_speed - 0.5, # Asteroids move slightly slower
                'color': color,
                'radius': radius
            })

    # ------------------------------------------
    # COLLISION DETECTION (AABB)
    # ------------------------------------------
    def check_aabb_collision(self, x1, y1, w1, h1, x2, y2, w2, h2):
        """
        Calculates if two axis-aligned bounding boxes overlap.
        (x1, y1) and (x2, y2) are the center positions of the boxes.
        """
        left1 = x1 - w1 / 2.0
        right1 = x1 + w1 / 2.0
        bottom1 = y1 - h1 / 2.0
        top1 = y1 + h1 / 2.0

        left2 = x2 - w2 / 2.0
        right2 = x2 + w2 / 2.0
        bottom2 = y2 - h2 / 2.0
        top2 = y2 + h2 / 2.0

        return (right1 > left2 and left1 < right2 and
                top1 > bottom2 and bottom1 < top2)

    # ------------------------------------------
    # CORE GAME LOOP - UPDATE FUNCTION
    # ------------------------------------------
    def update(self):
        """Updates game coordinates, registers key inputs, and evaluates collision mechanics."""
        if self.game_over:
            return

        # 1. Update stars
        self.update_stars()

        # 2. Update explosions
        self.update_explosions()

        # 3. Handle Player Movement
        # Restrict movement to keep the ship within visual screen boundaries
        if self.keys['left']:
            self.player_x -= self.player_speed
            if self.player_x < self.player_w:
                self.player_x = self.player_w
        if self.keys['right']:
            self.player_x += self.player_speed
            if self.player_x > self.width - self.player_w:
                self.player_x = self.width - self.player_w
        if self.keys['up']:
            self.player_y += self.player_speed
            # Restrict player to bottom half of the screen
            if self.player_y > self.height / 2.0:
                self.player_y = self.height / 2.0
        if self.keys['down']:
            self.player_y -= self.player_speed
            if self.player_y < self.player_h:
                self.player_y = self.player_h

        # 4. Handle Laser Firing & Cooldown
        if self.shoot_cooldown > 0:
            self.shoot_cooldown -= 1
        
        if self.keys['space'] and self.shoot_cooldown == 0:
            # Add a vertical laser projectile centered on the ship nose
            self.bullets.append({
                'x': self.player_x,
                'y': self.player_y + self.player_h / 2.0,
                'w': 6.0,
                'h': 20.0,
                'speed': 10.0
            })
            self.shoot_cooldown = 10 # Control firing speed (approx. 6 shots per sec at 60fps)

        # 5. Move Bullets and Clean up Offscreen Bullets
        for bullet in self.bullets[:]:
            bullet['y'] += bullet['speed']
            if bullet['y'] > self.height + 20:
                self.bullets.remove(bullet)

        # 6. Spawn and Move Enemies
        self.spawn_timer += 1
        # Dynamically scale spawning density based on current score
        spawn_interval = max(18, 50 - int(self.score / 50))
        if self.spawn_timer >= spawn_interval:
            self.spawn_enemy()
            self.spawn_timer = 0

        for enemy in self.enemies[:]:
            enemy['y'] -= enemy['speed']
            # Clean up off-screen enemies
            if enemy['y'] < -50:
                self.enemies.remove(enemy)

        # 7. Collision Resolution
        # Bullet vs. Enemy
        for bullet in self.bullets[:]:
            for enemy in self.enemies[:]:
                if self.check_aabb_collision(
                    bullet['x'], bullet['y'], bullet['w'], bullet['h'],
                    enemy['x'], enemy['y'], enemy['w'], enemy['h']
                ):
                    # Trigger visual explosion effect using enemy's native colors
                    self.spawn_explosion(enemy['x'], enemy['y'], enemy['color'])
                    
                    # Remove interacting entities
                    if bullet in self.bullets:
                        self.bullets.remove(bullet)
                    if enemy in self.enemies:
                        self.enemies.remove(enemy)
                    
                    # Add to player score
                    self.score += 15
                    break # Break inner loop since this bullet was destroyed

        # Player vs. Enemy
        for enemy in self.enemies:
            # We scale down player collision dimensions slightly to provide a fairer player boundary hitbox
            if self.check_aabb_collision(
                self.player_x, self.player_y, self.player_w * 0.7, self.player_h * 0.7,
                enemy['x'], enemy['y'], enemy['w'], enemy['h']
            ):
                # Trigger final player explosion
                self.spawn_explosion(self.player_x, self.player_y, (0.0, 0.9, 1.0))
                self.spawn_explosion(self.player_x, self.player_y, (1.0, 0.5, 0.0))
                
                # End game state
                self.game_over = True
                if self.score > self.high_score:
                    self.high_score = self.score
                break

        # 8. Score Increase Over Time (Survival Points)
        self.survival_timer += 1
        if self.survival_timer >= 30: # 1 point every 0.5 seconds at 60fps
            self.score += 1
            self.survival_timer = 0

    # ------------------------------------------
    # RENDER / DRAWING METHODS
    # ------------------------------------------
    def draw_player(self):
        """Draws a beautiful composite polygon spaceship with glowing engine thrusters."""
        x, y = self.player_x, self.player_y
        w, h = self.player_w, self.player_h

        # 1. Engine Flame (Flickering triangle)
        flame_h = random.randint(15, 25)
        glBegin(GL_TRIANGLES)
        glColor3f(1.0, 0.4, 0.0) # Vivid Orange
        glVertex2f(x - 6.0, y - h / 2.0)
        glVertex2f(x + 6.0, y - h / 2.0)
        glColor3f(1.0, 0.0, 0.0) # Red base
        glVertex2f(x, y - h / 2.0 - flame_h)
        glEnd()

        # 2. Side Wings (Triangles with purple/magenta highlights)
        glBegin(GL_TRIANGLES)
        # Left Wing
        glColor3f(0.5, 0.0, 0.8)
        glVertex2f(x - w / 4.0, y - h / 4.0)
        glColor3f(0.9, 0.2, 0.9)
        glVertex2f(x - w, y - h / 2.0)
        glColor3f(0.3, 0.0, 0.6)
        glVertex2f(x - w / 4.0, y - h / 2.0)
        glEnd()

        glBegin(GL_TRIANGLES)
        # Right Wing
        glColor3f(0.5, 0.0, 0.8)
        glVertex2f(x + w / 4.0, y - h / 4.0)
        glColor3f(0.3, 0.0, 0.6)
        glVertex2f(x + w / 4.0, y - h / 2.0)
        glColor3f(0.9, 0.2, 0.9)
        glVertex2f(x + w, y - h / 2.0)
        glEnd()

        # 3. Main Hull Cockpit (Triangle with sharp blue gradient)
        glBegin(GL_TRIANGLES)
        glColor3f(0.0, 0.9, 1.0) # Light blue cockpit tip
        glVertex2f(x, y + h / 2.0)
        glColor3f(0.0, 0.3, 0.8) # Royal blue left
        glVertex2f(x - w / 2.0, y - h / 2.0)
        glColor3f(0.0, 0.3, 0.8) # Royal blue right
        glVertex2f(x + w / 2.0, y - h / 2.0)
        glEnd()

        # 4. Glass Canopy Overlay
        glBegin(GL_TRIANGLES)
        glColor3f(0.8, 1.0, 1.0) # Bright cyan
        glVertex2f(x, y + h / 4.0)
        glColor3f(0.2, 0.6, 0.8) # Shadowed blue
        glVertex2f(x - w / 5.0, y - h / 6.0)
        glVertex2f(x + w / 5.0, y - h / 6.0)
        glEnd()

    def draw_enemy_block(self, enemy):
        """Draws a solid rectangular grid enemy with secondary core panels."""
        x, y, w, h = enemy['x'], enemy['y'], enemy['w'], enemy['h']
        r, g, b = enemy['color']

        # Outer armor plating
        glBegin(GL_QUADS)
        glColor3f(r, g, b)
        glVertex2f(x - w / 2.0, y - h / 2.0)
        glVertex2f(x + w / 2.0, y - h / 2.0)
        glColor3f(r * 0.4, g * 0.4, b * 0.4) # Shadows
        glVertex2f(x + w / 2.0, y + h / 2.0)
        glVertex2f(x - w / 2.0, y + h / 2.0)
        glEnd()

        # Core glowing cell
        glBegin(GL_QUADS)
        glColor3f(1.0, 1.0, 1.0) # Glowing white center
        glVertex2f(x - w / 6.0, y - h / 6.0)
        glVertex2f(x + w / 6.0, y - h / 6.0)
        glVertex2f(x + w / 6.0, y + h / 6.0)
        glVertex2f(x - w / 6.0, y + h / 6.0)
        glEnd()

    def draw_asteroid(self, enemy):
        """Draws a circular asteroid using a multi-colored triangle fan for rocky contours."""
        x, y = enemy['x'], enemy['y']
        radius = enemy['radius']
        r, g, b = enemy['color']

        glBegin(GL_TRIANGLE_FAN)
        glColor3f(r, g, b) # Rock center color
        glVertex2f(x, y)
        
        num_segments = 20
        for i in range(num_segments + 1):
            theta = 2.0 * math.pi * i / num_segments
            
            # Use fixed trigonometric seed multiplier to maintain shapes over frames
            roughness = 1.0 + 0.12 * math.sin(i * 2.3)
            rad = radius * roughness
            
            # Darken border colors to show shading
            c_mod = 0.6 + 0.4 * math.sin(i * 1.5)
            glColor3f(r * c_mod, g * c_mod, b * c_mod)
            
            dx = rad * math.cos(theta)
            dy = rad * math.sin(theta)
            glVertex2f(x + dx, y + dy)
        glEnd()

    def draw_bullets(self):
        """Draws player lasers with a hot vertical core styling."""
        for bullet in self.bullets:
            x, y, w, h = bullet['x'], bullet['y'], bullet['w'], bullet['h']
            glBegin(GL_QUADS)
            glColor3f(1.0, 0.1, 0.1) # Bright red base
            glVertex2f(x - w / 2.0, y - h / 2.0)
            glVertex2f(x + w / 2.0, y - h / 2.0)
            glColor3f(1.0, 1.0, 0.2) # White-hot yellow tip
            glVertex2f(x + w / 2.0, y + h / 2.0)
            glVertex2f(x - w / 2.0, y + h / 2.0)
            glEnd()

    def draw_stars(self):
        """Draws background stars."""
        glPointSize(2.0)
        glBegin(GL_POINTS)
        for star in self.stars:
            glColor3f(star['color'], star['color'], star['color'])
            glVertex2f(star['x'], star['y'])
        glEnd()

    def draw_explosions(self):
        """Draws particle effects with physical decay multipliers."""
        glPointSize(3.0)
        glBegin(GL_POINTS)
        for p in self.explosions:
            r, g, b = p['color']
            # Fade colors relative to lifetime
            glColor3f(r * p['life'], g * p['life'], b * p['life'])
            glVertex2f(p['x'], p['y'])
        glEnd()

    def draw_text(self, x, y, text, font=GLUT_BITMAP_HELVETICA_18, r=1.0, g=1.0, b=1.0):
        """Helper to print a string of characters using GLUT bitmap characters."""
        glColor3f(r, g, b)
        glRasterPos2f(x, y)
        for char in text:
            # We convert each char to integer ascii representation for pyopengl compatibility
            glutBitmapCharacter(font, ord(char))

    def render(self):
        """Parent draw caller executing layered rendering of background, entities, and menus."""
        # Clear color and depth buffer
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        # 1. Draw Starfield
        self.draw_stars()

        # 2. Draw Lasers
        self.draw_bullets()

        # 3. Draw Enemies
        for enemy in self.enemies:
            if enemy['type'] == 'block':
                self.draw_enemy_block(enemy)
            elif enemy['type'] == 'asteroid':
                self.draw_asteroid(enemy)

        # 4. Draw Explosions
        self.draw_explosions()

        # 5. Draw Player (If alive)
        if not self.game_over:
            self.draw_player()

        # 6. Draw HUD User Interface
        self.draw_text(20, self.height - 30, f"Score: {self.score}", GLUT_BITMAP_HELVETICA_18, 0.0, 1.0, 1.0)
        self.draw_text(self.width - 180, self.height - 30, f"High Score: {self.high_score}", GLUT_BITMAP_HELVETICA_18, 1.0, 0.8, 0.0)
        
        # 7. Draw Game Over Overlay
        if self.game_over:
            # Enable blending to draw a transparent overlay
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            
            # Dark transparent rectangle covering the board
            glColor4f(0.0, 0.0, 0.0, 0.75) # 75% opacity dark dim overlay
            glBegin(GL_QUADS)
            glVertex2f(0, 0)
            glVertex2f(self.width, 0)
            glVertex2f(self.width, self.height)
            glVertex2f(0, self.height)
            glEnd()
            
            glDisable(GL_BLEND) # Disable blending for solid text
            
            # Draw game menu items centered
            self.draw_text(self.width / 2.0 - 90, self.height / 2.0 + 60, "GAME OVER", GLUT_BITMAP_TIMES_ROMAN_24, 1.0, 0.2, 0.2)
            self.draw_text(self.width / 2.0 - 70, self.height / 2.0 + 10, f"Final Score: {self.score}", GLUT_BITMAP_HELVETICA_18, 1.0, 1.0, 1.0)
            self.draw_text(self.width / 2.0 - 100, self.height / 2.0 - 30, "Press 'R' to Restart", GLUT_BITMAP_HELVETICA_18, 0.0, 1.0, 0.5)
            self.draw_text(self.width / 2.0 - 95, self.height / 2.0 - 70, "Press 'ESC' to Quit", GLUT_BITMAP_HELVETICA_18, 0.7, 0.7, 0.7)

        # Swap back buffers to show drawn frame
        glutSwapBuffers()

# ==========================================
# GLUT CALLBACK WRAPPERS
# ==========================================

# Reference to the globally instanced game object
game = None

def display_func():
    """Wrapper display function executed continuously."""
    if game:
        game.render()

def timer_func(value):
    """Wrapper timer callback executing frame updates (approx. 60 FPS)."""
    if game:
        if not game.game_over:
            game.update()
        else:
            # Continue running starfield & particle effects even on Game Over
            game.update_stars()
            game.update_explosions()

        glutPostRedisplay() # Trigger redraw
    
    # Re-register timer function for the next frame
    glutTimerFunc(16, timer_func, 0)

def reshape_func(w, h):
    """Callback when window is resized. Maps logical 800x600 resolution to pixel space."""
    if game:
        game.width = w
        game.height = h
    glViewport(0, 0, w, h)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    # Lock coordinate mapping system to (0, 800) x (0, 600)
    gluOrtho2D(0.0, 800.0, 0.0, 600.0)
    glMatrixMode(GL_MODELVIEW)

# ------------------------------------------
# CONTROLS CALLBACK HANDLERS
# ------------------------------------------
def special_key_down(key, x, y):
    """Tracks special keys (Arrows) when pressed down."""
    if game:
        if key == GLUT_KEY_LEFT:
            game.keys['left'] = True
        elif key == GLUT_KEY_RIGHT:
            game.keys['right'] = True
        elif key == GLUT_KEY_UP:
            game.keys['up'] = True
        elif key == GLUT_KEY_DOWN:
            game.keys['down'] = True

def special_key_up(key, x, y):
    """Tracks special keys (Arrows) when released."""
    if game:
        if key == GLUT_KEY_LEFT:
            game.keys['left'] = False
        elif key == GLUT_KEY_RIGHT:
            game.keys['right'] = False
        elif key == GLUT_KEY_UP:
            game.keys['up'] = False
        elif key == GLUT_KEY_DOWN:
            game.keys['down'] = False

def keyboard_down(key, x, y):
    """Tracks normal ASCII keys when pressed down."""
    if game:
        # Spacebar to shoot lasers
        if key == b' ':
            game.keys['space'] = True
        # Restart key
        elif key in (b'r', b'R'):
            if game.game_over:
                game.reset_game()
        # Escape key to quit
        elif key == b'\x1b': # ASCII for ESC
            sys.exit(0)

def keyboard_up(key, x, y):
    """Tracks normal ASCII keys when released."""
    if game:
        if key == b' ':
            game.keys['space'] = False

# ==========================================
# MAIN EXECUTION BOILERPLATE
# ==========================================

def main():
    global game
    
    # 1. Initialize GLUT
    glutInit(sys.argv)
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    
    # 2. Window Setup
    glutInitWindowSize(800, 600)
    glutInitWindowPosition(100, 100)
    glutCreateWindow(b"Retro Space Shooter 2D")
    
    # 3. Initialize background color & OpenGL state
    glClearColor(0.03, 0.03, 0.08, 1.0) # Dark space blue/black
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluOrtho2D(0.0, 800.0, 0.0, 600.0)
    glMatrixMode(GL_MODELVIEW)
    
    # Instantiate global game tracker
    game = SpaceShooterGame()
    
    # 4. Register GLUT Callback loops
    glutDisplayFunc(display_func)
    glutReshapeFunc(reshape_func)
    glutTimerFunc(16, timer_func, 0) # 16ms delay is approx. 60 FPS
    
    # Input event triggers
    glutSpecialFunc(special_key_down)
    glutSpecialUpFunc(special_key_up)
    glutKeyboardFunc(keyboard_down)
    glutKeyboardUpFunc(keyboard_up)
    
    # 5. Start main loop
    glutMainLoop()

if __name__ == '__main__':
    main()
