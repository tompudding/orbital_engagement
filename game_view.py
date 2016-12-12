from OpenGL.GL import *
import random,numpy,cmath,math,pygame

import ui,globals,drawing,os,copy
from globals.types import Point
import modes
import random
import cmath

G = 1


class Viewpos(object):
    follow_threshold = 0
    max_away = 250
    def __init__(self,point):
        self.pos = point
        self.NoTarget()
        self.follow = None
        self.follow_locked = False
        self.t = 0

    def NoTarget(self):
        self.target        = None
        self.target_change = None
        self.start_point   = None
        self.target_time   = None
        self.start_time    = None

    def Set(self,point):
        self.pos = point
        #self.NoTarget()

    def SetTarget(self,point,t,rate=2,callback = None):
        #Don't fuck with the view if the player is trying to control it
        rate /= 4.0
        self.follow        = None
        self.follow_start  = 0
        self.follow_locked = False
        self.target        = point
        self.target_change = self.target - self.pos
        self.start_point   = self.pos
        self.start_time    = t
        self.duration      = self.target_change.length()/rate
        self.callback      = callback
        if self.duration < 200:
            self.duration  = 200
        self.target_time   = self.start_time + self.duration

    def Follow(self,t,actor):
        """
        Follow the given actor around.
        """
        self.follow        = actor
        self.follow_start  = t
        self.follow_locked = False

    def HasTarget(self):
        return self.target != None

    def Get(self):
        return self.pos

    def Skip(self):
        self.pos = self.target
        self.NoTarget()
        if self.callback:
            self.callback(self.t)
            self.callback = None

    def Update(self,t):
        try:
            return self.update(t)
        finally:
            self.pos = self.pos.to_int()

    def update(self,t):
        self.t = t
        if self.follow:
            if self.follow_locked:
                self.pos = self.follow.GetPos() - globals.screen*0.5
            else:
                #We haven't locked onto it yet, so move closer, and lock on if it's below the threshold
                fpos = self.follow.GetPos()*globals.tile_dimensions
                if not fpos:
                    return
                target = fpos - globals.screen*0.5
                diff = target - self.pos
                if diff.SquareLength() < self.follow_threshold:
                    self.pos = target
                    self.follow_locked = True
                else:
                    distance = diff.length()
                    if distance > self.max_away:
                        self.pos += diff.unit_vector()*(distance*1.02-self.max_away)
                        newdiff = target - self.pos
                    else:
                        self.pos += diff*0.02

        elif self.target:
            if t >= self.target_time:
                self.pos = self.target
                self.NoTarget()
                if self.callback:
                    self.callback(t)
                    self.callback = None
            elif t < self.start_time: #I don't think we should get this
                return
            else:
                partial = float(t-self.start_time)/self.duration
                partial = partial*partial*(3 - 2*partial) #smoothstep
                self.pos = (self.start_point + (self.target_change*partial)).to_int()


class Body(object):
    def __init__(self, pos, velocity, type, mass, last_pos = None):
        self.pos = pos
        self.velocity = velocity
        self.mass = mass
        self.type = type
        self.acc = Point(0,0)
        if last_pos:
            self.line_seg = drawing.Line(globals.line_buffer)
            self.line_seg.SetVertices( last_pos , self.pos, 1000 )
            intensity = 1
            col = line_colours[type] + (1, )
            self.line_seg.SetColour( col )
        self.temp_bodies = []

    def step(self, elapsed, gravity_sources, line=True):
        acc = self.acc
        for body in gravity_sources:
            acc += body.acc_due_to_gravity(self)

        velocity = self.velocity + (acc * elapsed)
        distance_travelled = self.velocity * elapsed

        pos = self.pos + (distance_travelled * globals.units_to_pixels)

        return Body(pos, velocity, self.type, self.mass, self.pos if line else None)

    def set_force(self, force):
        new_acc = force * globals.pixels_to_units
        if (new_acc - self.acc).SquareLength() < 10:
            changed = False
        else:
            changed = True
        self.acc = new_acc
        return changed

    def acc_due_to_gravity(self, body):
        vector = (self.pos - body.pos) * globals.pixels_to_units
        return (vector.unit_vector() / vector.SquareLength()) * self.mass * G

    def apply_force_towards(self, target, force):
        vector = ((target.pos - self.pos).unit_vector())
        acc = ((vector * force)/ self.mass)
        self.velocity += acc

    def scan_for_target(self, target, min_distance):
        #Throw out a bunch of rays and see if any of them collide with the player's current ray
        diff = target.pos - self.pos
        distance, angle_to_player = cmath.polar(diff[0] + diff[1]*1j)
        gap = math.pi/32
        angle_guesses = [angle_to_player + i*gap for i in xrange(-16,16)]
        # for b in self.temp_bodies:
        #    b.line_seg.Delete()
        # self.temp_bodies = []
        period = 40000.0
        best_time = period
        firing_angle = None
        target_type = target.type
        for angle in angle_guesses:
            body = self
            v = cmath.rect(globals.game_view.missile_speed, angle)
            velocity = Point(v.real, v.imag)
            body = Body(body.pos, body.velocity + velocity, body.type, body.mass)
            step = 1000
            t = globals.time


            while t < globals.time + period:
                target = globals.game_view.get_obj_at_time( target_type, t )
                if target:
                    #don't get too close to the sun
                    distance = (target.pos - body.pos).length()
                    if distance < min_distance and (t - globals.time) < best_time:
                        best_time = t - globals.time
                        firing_angle = angle
                    #body.apply_force_towards( target, 1 )

                body = body.step(step * globals.time_factor, globals.game_view.fixed_bodies, line = False)
                if body.pos.length() < 30:
                    #print 'rejecting path',body.pos.length()
                    break
                #self.temp_bodies.append(body)
                t += step
        # for body in self.temp_bodies:
        #     body.line_seg.SetColour( (1,1,1,1) )
        if firing_angle is None:
            return None
        return firing_angle, best_time

class FixedBody(Body):
    def step(self, gravity_sources):
        #Fixed bodies don't change
        return self

class BodyImage(object):
    def __init__(self):
        self.quad = drawing.Quad(globals.quad_buffer, tc=globals.atlas.TextureSpriteCoords(self.texture_name))
        self.enabled = True

    def Disable(self):
        if self.enabled:
            self.enabled = False
            self.quad.Disable()

    def Enable(self):
        if not self.enabled:
            self.enabled = True
            self.quad.Enable()


    def set_vertices(self, pos):
        bl = pos - Point(16,16)
        tr = bl + Point(32,32)
        self.quad.SetVertices(bl, tr, self.height)


class Sun(BodyImage):
    height = 9000
    texture_name = 'sun.png'

class Ship(BodyImage):
    texture_name = 'ship.png'
    mass = 100
    height = 8000

class Enemy(Ship):
    texture_name = 'enemy.png'
    scan_line_parts = 32
    scan_radius = 150
    scan_duration = 500.0
    def __init__(self, *args, **kwargs):
        super(Enemy, self).__init__(*args, **kwargs)
        self.locked = False
        #Inert like an asteroid
        self.active = False
        self.has_lock = False
        self.scan_start = None
        self.scan_lines = [drawing.Line(globals.line_buffer) for i in xrange(self.scan_line_parts)]
        self.last_launch = None

    def Disable(self):
        if self.enabled:
            self.enabled = False
            self.quad.Disable()
            for line in self.scan_lines:
                line.Delete()

    def Enable(self):
        if not self.enabled:
            self.enabled = True
            self.quad.Enable()
            self.scan_lines = [drawing.Line(globals.line_buffer) for i in xrange(self.scan_line_parts)]


class Missile(BodyImage):
    texture_name = 'missile.png'
    mass = 1
    height = 8500

class Objects:
    SUN  = 0
    PLAYER = 1
    ENEMY  = 2
    MISSILE1 = 3
    MISSILE2 = 4
    MISSILE3 = 5
    MISSILE4 = 6
    MISSILE5 = 7

    missiles = [MISSILE1, MISSILE2, MISSILE3, MISSILE4, MISSILE5]
    mobile = [PLAYER, ENEMY]

line_colours = { Objects.PLAYER : (0,0,1),
                 Objects.MISSILE1 : (0.2,0.2,0.2),
                 Objects.ENEMY  : (1,0,0) }

for i in xrange(Objects.MISSILE5 + 1, Objects.MISSILE5 + 100):
    Objects.missiles.append(i)

Objects.mobile += Objects.missiles

for t in Objects.missiles:
    line_colours[t] = line_colours[Objects.MISSILE1]

class Menu(object):
    def __init__(self, parent):
        bl = parent.GetRelative(globals.screen/-2.0)

        self.frame = ui.UIElement(parent=parent,
                                  pos=bl,
                                  tr=bl*-1
                                  )
        self.title = ui.TextBox( parent=self.frame,
                                 bl=Point(0.05,0.75),
                                 tr=None,
                                 text='ORBITAL ENGAGEMENT',
                                 textType = drawing.texture.TextTypes.GRID_RELATIVE,
                                 colour = (0,0.7,0,1),
                                 scale = 16)

        self.level_names = ['0 : Tutorial',
                            '1 : Asteroid Defence',
                            '2 : Probes',
                            '3 : Live Fire',
                            '4 : Targeting',
                            '5 : Into the unknown']
        self.level_text = []
        pos = 0.6
        for i,name in enumerate(self.level_names):
            text = ui.TextBox( parent=self.frame,
                               bl=Point(0.15,pos -i*0.1),
                               tr=None,
                               text=name,
                               textType = drawing.texture.TextTypes.GRID_RELATIVE,
                               colour = (0,0.7,0,1),
                               scale = 12)
            selected_button = ui.TextBox( parent=self.frame,
                                          bl=Point(0.10,pos +0.005 -i*0.1),
                                          tr=None,
                                          text=' ',
                                          textType = drawing.texture.TextTypes.GRID_RELATIVE,
                                          colour = (0,0.7,0,1),
                                          scale = 12)
            self.level_text.append((selected_button,text))
        self.death_text = ui.TextBox( parent=self.frame,
                                      bl=Point(0.3,0.45),
                                      tr=None,
                                      text='YOU DIED',
                                      textType = drawing.texture.TextTypes.GRID_RELATIVE,
                                      colour = (0.7,0.1,0,1),
                                      scale = 16)
        self.death_text.Disable()
        self.win_text = ui.TextBox( parent=self.frame,
                                      bl=Point(0.3,0.45),
                                      tr=None,
                                      text='YOU WON',
                                      textType = drawing.texture.TextTypes.GRID_RELATIVE,
                                      colour = (0.7,0.1,0,1),
                                      scale = 16)
        self.win_text.Disable()
        self.again_text = ui.TextBox( parent=self.frame,
                                      bl=Point(0.2,0.3),
                                      tr=None,
                                      text='Press fire to play again',
                                      textType = drawing.texture.TextTypes.GRID_RELATIVE,
                                      colour = (0,0.7,0,1),
                                      scale = 8)
        self.again_text.Disable()
        self.selected = None
        self.splash = False
        self.select(0)

    def show_win_screen(self):
        #We need to disable the menu items
        self.show_splash(self.win_text)

    def show_die_screen(self):
        self.show_splash(self.death_text)

    def show_splash(self, item):
        self.win_text.Disable()
        self.death_text.Disable()
        self.again_text.Enable()

        item.Enable()
        self.splash = item
        for a,b in self.level_text:
            a.Disable()
            b.Disable()
        self.title.Disable()

    def hide_splash(self):
        self.win_text.Disable()
        self.death_text.Disable()
        self.again_text.Disable()
        self.splash = False
        for a,b in self.level_text:
            a.Enable()
            b.Enable()
        self.title.Enable()
        self.win_text.Disable()
        self.death_text.Disable()

    def select(self, n):
        if self.splash:
            return
        if n == self.selected:
            return
        if self.selected is not None:
            #Disable the current one
            self.level_text[self.selected][0].SetText(' ')
        self.selected = n
        self.level_text[self.selected][0].SetText('\x9f')

    def key_press(self, key):
        if key == pygame.K_UP:
            new = self.selected - 1
            if new < 0:
                new = len(self.level_text) - 1
        elif key == pygame.K_DOWN:
            new = self.selected + 1
            if new == len(self.level_text):
                new = 0
        else:
            return
        globals.sounds.menu2.play()
        self.select(new)

    def choose(self):
        if self.splash:
            self.hide_splash()
            return
        globals.sounds.choose.play()
        globals.game_view.Reset( self.selected )

    def Enable(self):
        self.frame.Enable()
        if self.splash:
            self.show_splash(self.splash)
        else:
            self.hide_splash()

    def Disable(self):
        self.frame.Disable()



class Explosion(object):
    line_segs = 32
    def __init__(self, line_buffer, start, end, pos, radius, colour):
        self.lines = [drawing.Line(line_buffer) for i in xrange(self.line_segs)]
        self.start = start
        self.radius = radius
        self.end = end
        self.duration = float(end - start)
        self.pos = pos
        self.colour = colour

    def Update(self):
        partial = (globals.time - self.start) / self.duration
        r = self.radius * partial
        angles = [i*math.pi*2/self.line_segs for i in xrange(self.line_segs)]
        v = cmath.rect(r, angles[0])
        last = self.pos + Point(v.real, v.imag)
        for i in xrange(self.line_segs):
            angle = angles[(i + 1) % len(angles)]
            v = cmath.rect(r, angle)
            p = self.pos + Point(v.real, v.imag)
            self.lines[i].SetVertices( last, p, 10000 )
            last = p
            intensity = 1 - partial
            self.lines[i].SetColour( self.colour + (intensity,))
        if globals.time > self.end:
            for line in self.lines:
                line.Delete()
            return False
        return True

    def Delete(self):
        for line in self.lines:
            line.Delete()

class Echo(object):
    duration = 1000.0
    height = 9000
    def __init__(self, pos, t):
        self.pos = pos
        self.t = t
        self.quad = drawing.Quad(globals.quad_buffer, tc=globals.atlas.TextureSpriteCoords('enemy.png'))
        bl = pos - Point(16,16)
        tr = bl + Point(32,32)
        self.quad.SetVertices(bl, tr, self.height)
        self.quad.SetColour( (1,1,1,1) )
        self.deleted = False

    def update(self):
        if self.deleted:
            return False
        elapsed = globals.time - self.t
        if elapsed > self.duration:
            self.Delete()
            return False
        partial = elapsed / self.duration
        self.quad.SetColour( (1,1,1,1-partial) )
        return True

    def Delete(self):
        if not self.deleted:
            self.deleted = True
            self.quad.Delete()


class Keypad(object):
    positions = {'0'  : Point(0,0),
                 '.'  : Point(1,0),
                 'E' : Point(2,0),
                 '1'  : Point(0,1),
                 '2'  : Point(1,1),
                 '3'  : Point(2,1),
                 '4'  : Point(0,2),
                 '5'  : Point(1,2),
                 '6'  : Point(2,2),
                 '7'  : Point(0,3),
                 '8'  : Point(1,3),
                 '9'  : Point(2,3)}
    unit_vector = Point(28,26)

    def __init__(self, parent, bl, callback):
        uv = parent.GetRelative(self.unit_vector)
        self.buttons = []
        for char, pos in self.positions.iteritems():
            button = ui.ImageBoxButton(parent,
                                       bl + uv * pos,
                                       ('button_up_%s.png' % char,'button_down_%s.png' % char),
                                       lambda a,b,c,n=char: callback(n))
            self.buttons.append(button)


class Console(object):
    char_duration = 10
    flash_duration = 400
    def __init__(self, parent, pos):
        self.rows = []
        self.parent = parent
        for i in xrange(9):
            bl = pos - Point(0,0.015*i)
            tr = bl + Point(0.153,0.18)
            box = ui.TextBox(parent = globals.screen_root,
                             bl     = bl         ,
                             tr     = tr         ,
                             text   = ' '  ,
                             textType = drawing.texture.TextTypes.SCREEN_RELATIVE,
                             colour = (0,1,0,1),
                             scale  = 4)
            self.rows.append(box)
        self.width = 22
        self.pos = Point(0,0)
        self.buffer = []
        self.last = globals.time
        self.toggle = False
        self.saved_char = ' '
        #for text entry
        self.entering = False

    def clear(self):
        for row in self.rows:
            row.SetText(' ')
        self.pos = Point(0,0)
        self.last = globals.time
        self.unflash()

    def flash(self):
        self.saved_char = self.get_char(self.pos)
        self.set_char(self.pos, '\x9f')

    def unflash(self):
        self.set_char(self.pos, self.saved_char)
        self.saved_char = ' '

    def get_char(self, pos):
        if pos.x < self.width:
            text = ''.join(self.rows[pos.y].text)
            text = [c for c in text.ljust(self.width)[:self.width]]
            return text[pos.x]
        return ' '

    def set_char(self, pos, char):
        if pos.x < self.width:
            text = ''.join(self.rows[pos.y].text)
            text = [c for c in text.ljust(self.width)[:self.width]]
            text[pos.x] = char
            self.rows[pos.y].SetText(''.join(text))

    def add_char(self, char):
        if self.toggle:
            #Turn it off for now
            self.unflash()

        if char == ' ' and self.pos.x == 0:
            return

        if char != '\n':
            self.set_char(self.pos, char)

            self.pos.x += 1
            if self.pos.x >= self.width:
                self.pos.x = 0
                self.pos.y += 1
        else:
            self.pos.y += 1
            self.pos.x = 0
            self.last = globals.time
            if not self.toggle:
                self.toggle = True

        if self.pos.y >= len(self.rows):
            #move everything up one
            self.pos.y -= 1
            for i in xrange(len(self.rows) - 1):
                self.rows[i].SetText(self.rows[i+1].text)
            self.rows[len(self.rows) - 1].SetText(' ')
        if self.toggle:
            self.flash()

    def add_text(self, line, duration=None):
        if duration is None:
            duration = self.char_duration
        if not line.endswith('\n'):
            line = line + '\n'
        self.buffer.extend( [(c,globals.time + i*duration) for i,c in enumerate(line)] )

    def update(self):
        if globals.time - self.last > self.flash_duration:
            self.last = globals.time
            if self.toggle:
                self.toggle = False
                #turn off thing
                self.unflash()
            else:
                self.toggle = True
                #turn on thing
                self.flash()

        i = -1
        for i in xrange(len(self.buffer)):
            c,t = self.buffer[i]
            if t < globals.time:
                self.add_char(c)
            else:
                break
        else:
            self.buffer = []

        self.buffer = self.buffer[i:]

class GameView(ui.RootElement):
    step_time = 500
    trail_age = 60000.0
    trail_fade = 8000.0
    scan_duration = 500.0
    scan_line_parts = 32
    scan_radius = 150
    explosion_radius = 30
    explosion_duration = 125
    stabalise_duration = 2000
    missile_speed = 200
    no_overlay = (0,0,0,0)
    disabled_colour = (0,0,0,0.5)
    alert_colour = (1,0,0,0.5)

    def __init__(self):
        self.atlas = globals.atlas = drawing.texture.TextureAtlas('tiles_atlas_0.png','tiles_atlas.txt')
        globals.ui_atlas = drawing.texture.TextureAtlas('ui_atlas_0.png','ui_atlas.txt',extra_names=False)
        self.game_over = False
        self.tutorial = False
        pygame.mixer.music.load(os.path.join('resource','sounds','music_normal.ogg'))

        self.music_playing = False
        super(GameView,self).__init__(Point(0,0),globals.screen*4)
        #self.square = drawing.Line(globals.line_buffer)
        #self.square.SetVertices( Point(0,0), Point(1000,1000), 1000)
        #self.square.SetColour( (1,0,0,1) )
        self.explosion_line_buffer = drawing.LineBuffer(32000*Explosion.line_segs)
        self.sun = Sun()
        self.ship = Ship()
        self.enemy = Enemy()
        self.thrusters = True
        self.grid = ui.Grid(self,Point(-1,-1),Point(1,1),Point(40,40))
        self.grid.Enable()
        self.sun_body  = FixedBody( pos=Point(0,0), velocity=Point(0,0), type=Objects.SUN, mass=100000000 )
        self.sun.set_vertices(self.sun_body.pos)
        self.echoes = []
        self.lock_time = None
        self.no_auto_target = False

        self.initial_data = [
            #For the tutorial the asteroid is just behind the player in the orbit so they don't go out of sync
            { Objects.PLAYER : (
                    Point(100, 0),
                    Point(0,-1) * self.circular_orbit_velocity(100)
                    ),
              Objects.ENEMY  : (
                    Point(110, 0).Rotate(1.2),
                    Point(0,-1).Rotate(1.2) * self.circular_orbit_velocity(110),
                    False
                    ),
              },
            #Level 1 has the asteroid a bit further out in an ecliptic orbit
            { Objects.PLAYER : (
                        Point(100, 0),
                        Point(0,-1) * self.circular_orbit_velocity(100)
                        ),
              Objects.ENEMY  : (
                        Point(120, 120),
                        (Point(1,-1).unit_vector()) * 100,
                        False )
              },
            #Level 2 has the asteroid on the opposite side of the sun
              { Objects.PLAYER : (
                    Point(120, 0),
                    Point(0,-1) * self.circular_orbit_velocity(120)
                    ),
                Objects.ENEMY  : (
                    Point(120, 0).Rotate(math.pi),
                    Point(0,-1).Rotate(math.pi) * self.circular_orbit_velocity(120),
                    False
                    ),
                },
            #Level 3 has A live fire target on the opposite side of the sun
            { Objects.PLAYER : (
                    Point(120, 0),
                    Point(0,-1) * self.circular_orbit_velocity(120)
                    ),
                Objects.ENEMY  : (
                    Point(120, 0).Rotate(math.pi),
                    Point(0,-1).Rotate(math.pi) * self.circular_orbit_velocity(120),
                    True
                    ),
              },
            #Level 4 is the asteroid but manual targeting
            { Objects.PLAYER : (
                    Point(90, 0),
                    Point(0,-1) * self.circular_orbit_velocity(120)
                    ),
              Objects.ENEMY  : (
                    Point(120, 0).Rotate(0.1),
                    Point(0,-1).Rotate(math.pi) * self.circular_orbit_velocity(60),
                    False
                    ),
              },
            #Level 5 is the asteroid but manual targeting
            { Objects.PLAYER : (
                    Point(90, 0),
                    Point(0,-1) * self.circular_orbit_velocity(120)
                    ),
              Objects.ENEMY  : (
                    Point(120, 0).Rotate(0.1),
                    Point(0,-1).Rotate(math.pi) * self.circular_orbit_velocity(60),
                    True
                    ),
              }
            ]

        self.intro_text = ['Welcome to the orbital defence simulator private! Get used to this room as it\'s all you\'ll see for the rest of, er, I mean the next few days of, your life.\nClick here to begin',
                           'There\'s an asteroid nearby. Go get it son',
                           'Your thrusters have been disabled. Adversity builds character',
                           'Good news, your thrusters are back. Bad news, the asteroid has missiles',
                           'Automatic targeting has been disabled, good luck',
                           'A rogue asteroid with missiles is going crazy. Oh and your targeting is down'
                           ]

        self.ship_body = Body( Point(1, 0), Point(0,0), type=Objects.PLAYER, mass=1 )
        self.enemy_body = Body( Point(1, 0), Point(0,0), type=Objects.ENEMY, mass=1 )

        self.fixed_bodies = [self.sun_body]
        self.missile_images = [Missile() for i in xrange(len(Objects.missiles))]
        self.initial_state = { Objects.PLAYER : self.ship_body,
                               Objects.ENEMY  : self.enemy_body,
                               Objects.SUN    : self.sun_body }
        self.object_quads = { Objects.PLAYER : self.ship,
                              Objects.ENEMY : self.enemy }
        for (i,obj) in enumerate(Objects.missiles):
            self.object_quads[obj] = self.missile_images[i]


        self.trail_properties = { Objects.PLAYER : (60000.0, 8000.0),
                                  Objects.ENEMY  : (60000.0, 8000.0) }
        for t in Objects.missiles:
            self.trail_properties[t] = (0,400.0)

        self.menu = Menu(self)

        self.scan_lines = [drawing.Line(globals.line_buffer) for i in xrange(self.scan_line_parts)]
        #set up the state
        self.future_state = []
        #skip titles for development of the main game
        #self.mode = modes.Titles(self)
        self.viewpos = Viewpos(Point(-320,-180))
        self.dragging = None
        self.zoom = 1
        self.zooming = None
        self.last = None
        self.detonation_times = {}
        self.explosions = []

        self.mode = modes.Combat(self)
        self.saved_segs = { t : [] for t in Objects.mobile }

        self.scan_start = None
        self.move_direction = Point(0,0)
        self.console = Console(self, Point(0.0328125,0.0395) )

        self.keypad = Keypad(globals.screen_root,
                             Point(0.2,0.075),
                             self.keypad_pressed)

        self.scan_button = ui.ImageBoxButton(globals.screen_root,
                                             Point(0.43,0.15),
                                             ('button_scan.png','button_scan_pressed.png'),
                                             lambda a,b,c: self.start_scan())
        self.stabalise_button = ui.ImageBoxButton(globals.screen_root,
                                                  Point(0.43,0.07),
                                                  ('button_stabalise.png','button_stabalise_pressed.png'),
                                                  lambda a,b,c: self.hit_stabalise())


        self.manual_button = ui.ManualButton(globals.screen_root,
                                                     Point(0.3,0.06),
                                                     ('toggle_off.png','toggle_on.png'),
                                                     self.manual_firing)

        bl = Point(0.73,0.07)
        self.missile_button = ui.ImageBoxToggleButton(globals.screen_root,
                                                      bl + Point(0,0.08),
                                                      ('button_missile.png','button_missile_pressed.png'),
                                                      lambda state,weapon=0: self.select_weapon(state, weapon))

        self.probe_button = ui.ImageBoxToggleButton(globals.screen_root,
                                                    bl + Point(0,0),
                                                    ('button_probe.png','button_probe_pressed.png'),
                                                    lambda state,weapon=1: self.select_weapon(state, weapon))

        self.nuke_button = ui.ImageBoxToggleButton(globals.screen_root,
                                                   bl + Point(0.12,0.08),
                                                   ('button_nuke.png','button_nuke_pressed.png'),
                                                   lambda state,weapon=2: self.select_weapon(state, weapon))

        self.chaff_button = ui.ImageBoxToggleButton(globals.screen_root,
                                                    bl + Point(0.12,0),
                                                    ('button_chaff.png','button_chaff_pressed.png'),
                                                    lambda state,weapon=3: self.select_weapon(state, weapon))

        self.weapon_buttons = [self.missile_button, self.probe_button, self.nuke_button, self.chaff_button]
        self.weapon_names = ['Missile','Probe','Nuke','Chaff']
        self.arm_button = ui.ImageBoxButton(globals.screen_root,
                                            Point(0.836,0.125),
                                            ('button_up_..png','button_down_..png'),
                                            lambda a,b,c: self.arm_weapon())

        self.weapon_arm_times = [1000, #missile
                                 1500, #probe
                                 5000, #nuke
                                 200] #chaff

        bl = Point(0.48,0.085)
        self.thrust_up_button = ui.ThrustButton(globals.screen_root,
                                                  bl + Point(0.1,0.07),
                                                  ('thruster_up.png','thruster_up_pressed.png'),
                                                  lambda a,b,c,d,key=pygame.K_UP: self.thrust(d, key))
        self.thrust_down_button = ui.ThrustButton(globals.screen_root,
                                                    bl + Point(0.1,0.0),
                                                    ('thruster_down.png','thruster_down_pressed.png'),
                                                    lambda a,b,c,d,key=pygame.K_DOWN: self.thrust(d, key))
        self.thrust_left_button = ui.ThrustButton(globals.screen_root,
                                                    bl + Point(0.07,0.035),
                                                    ('thruster_left.png','thruster_left_pressed.png'),
                                                    lambda a,b,c,d,key=pygame.K_LEFT: self.thrust(d, key))
        self.thrust_right_button = ui.ThrustButton(globals.screen_root,
                                                     bl + Point(0.13,0.035),
                                                     ('thruster_right.png','thruster_right_pressed.png'),
                                                     lambda a,b,c,d,key=pygame.K_RIGHT: self.thrust(d, key))

        self.key_to_thrust = { pygame.K_UP : self.thrust_up_button,
                               pygame.K_DOWN : self.thrust_down_button,
                               pygame.K_LEFT : self.thrust_left_button,
                               pygame.K_RIGHT : self.thrust_right_button }


        bl = Point(0.8,0.01)
        tr = bl + Point(0.1,0.03)
        self.arm_progress = ui.PowerBar(globals.screen_root,
                                        pos = bl,
                                        tr = tr,
                                        level = 0,
                                        bar_colours = (drawing.constants.colours.red,
                                                       drawing.constants.colours.yellow,
                                                       drawing.constants.colours.green),
                                        border_colour = (0,0,0,0.4))

        self.fire_button = ui.FireButton(globals.screen_root,
                                         Point(0.652,0.11),
                                         ('fire_button_up.png','fire_button_down.png'),
                                         lambda a,b,c: self.fire())

        self.StartMusic()
        self.stabalise_orbit(Objects.ENEMY)
        self.finish_stabalising = None
        self.disabled = False
        self.overlay = drawing.Quad(globals.colour_tiles)
        self.overlay.SetVertices(Point(0,0), globals.screen_abs, 10000)
        self.overlay.SetColour(self.no_overlay)
        bl = Point(0.278,0.106)
        tr = bl + Point(0.08,0.08)
        self.bearing_text = ui.TextBox(parent = globals.screen_root,
                                       bl     = bl         ,
                                       tr     = tr         ,
                                       text   = '---.-',
                                       textType = drawing.texture.TextTypes.SCREEN_RELATIVE,
                                       colour = (0,1,0,1),
                                       scale  = 8)

        bl = Point(0.278,0.061)
        tr = bl + Point(0.08,0.08)
        self.fuse_text = ui.TextBox(parent = globals.screen_root,
                                    bl     = bl         ,
                                    tr     = tr         ,
                                    text   = '---.-',
                                    textType = drawing.texture.TextTypes.SCREEN_RELATIVE,
                                    colour = (0,1,0,1),
                                    scale  = 8)

        self.firing_solution = None
        self.selected_weapon = None
        self.arm_end = None
        self.firing_solution_steps = []

        self.Stop()

    def tutorial_click_screen(self):
        self.console.add_text('Great. You\'re in orbit around a star and there\'s an asteroid behind you. Click scan to find it\n\n')
        self.tutorial = self.tutorial_click_scan

    def tutorial_click_scan(self):
        self.console.add_text('You\'re now locked on. Drag the screen to look around a little.\n\n')
        self.tutorial = self.tutorial_drag

    def tutorial_drag(self):
        self.console.add_text('Nice. You\'re targeting solution is locked in, but to fire you need to arm a weapon. Choose missile and hit the arm button in the middle\n\n')
        self.tutorial = self.tutorial_arm

    def tutorial_arm(self):
        self.console.add_text('Now you\'re locked and weapons are armed.\nFire when ready.\n\n')
        self.tutorial = self.tutorial_fire

    def tutorial_fire(self):
        self.console.add_text('Great, your missile is away. It may take a few hits to destroy it, good luck\n\n')
        self.tutorial = False

    def circular_orbit_velocity(self, r):
        return (math.sqrt(G * self.sun_body.mass / (r * globals.pixels_to_units)))

    def Reset(self, level):
        self.Stop()
        #Reset the data
        rotation = random.random()*math.pi*2
        pos,velocity = self.initial_data[level][Objects.PLAYER]
        self.ship_body.pos = pos.Rotate(rotation)
        self.ship_body.velocity = velocity.Rotate(rotation)

        pos,velocity,active = self.initial_data[level][Objects.ENEMY]
        self.thrusters = False if level == 2 else True
        #amazing hack to toggle the button to on while stopped
        self.stopped = False
        if level in [4,5]:
            self.manual_button.OnClick(None,None)
            self.no_auto_target = True
        else:
            self.no_auto_target = False
        self.stopped = True

        self.enemy_body.pos = pos.Rotate(rotation)
        self.enemy_body.velocity = velocity.Rotate(rotation)
        self.enemy = Enemy()
        self.enemy.active = active
        if self.enemy.active:
            #The last music was aggressive, put the normal one back on
            pygame.mixer.music.load(os.path.join('resource','sounds','music_action.ogg'))
            self.music_playing = False
            self.StartMusic()
        self.viewpos = Viewpos(Point(-320,-180))
        self.dragging = None
        self.zoom = 1
        self.zooming = None
        self.detonation_times = {}
        self.explosions = []
        self.enemy.locked = False
        self.firing_solution = None
        self.selected_weapon = None
        self.arm_end = None
        self.firing_solution_steps = []
        self.arm_progress.SetBarLevel(0)
        self.player_health = 100
        self.enemy_health = 100
        self.end_time = None
        self.lock_time = None
        self.console.clear()
        self.echoes = []
        self.scan_lines = [drawing.Line(globals.line_buffer) for i in xrange(self.scan_line_parts)]
        self.scan_start = None
        self.console.add_text(self.intro_text[level])
        self.initial_state = { Objects.PLAYER : self.ship_body,
                               Objects.ENEMY  : self.enemy_body,
                               Objects.SUN    : self.sun_body }
        if level == 0:
            self.tutorial = self.tutorial_click_screen
        else:
            self.tutorial = False
        self.Start()

        #self.Stop()

    def Stop(self):
        #reset the buttons before we stop it since they don't work when stopped
        if self.enemy.active:
            #The last music was aggressive, put the normal one back on
            pygame.mixer.music.load(os.path.join('resource','sounds','music_normal.ogg'))
            self.music_playing = False
            self.StartMusic()
        self.thrusters = True
        for button in self.weapon_buttons:
            if button.state:
                button.OnClick(None,None,skip_callback=True)
        self.no_auto_target = False
        if self.manual_button.state:
            self.manual_button.OnClick(None, None, skip_callback=True)
        self.stopped = True
        #Disable all the lines and we'll just not draw the quads
        self.sun.Disable()
        self.ship.Disable()
        self.enemy.Disable()
        for line in self.scan_lines:
            line.Delete()
        for m in self.missile_images:
            m.Disable()
        for echo in self.echoes:
            echo.Delete()
        for obj_type in Objects.mobile:
            for i in xrange(0, len(self.future_state)):
                try:
                    self.future_state[i][1][obj_type].line_seg.Delete()
                except KeyError:
                    continue
            #Also the saved segs
            if obj_type not in self.saved_segs:
                continue
            for (t,line_seg) in self.saved_segs[obj_type]:
                line_seg.Delete()
        #Finally the firing solution line
        for body in self.firing_solution_steps:
            body.line_seg.Delete()
        for exp in self.explosions:
            exp.Delete()
        self.future_state = []
        self.viewpos = Viewpos(Point(-320,-180))

        #For the menu
        self.fire_button.arm()
        self.menu.Enable()

    def Start(self):
        self.stopped = False
        self.menu.Disable()
        self.sun.Enable()
        self.ship.Enable()
        self.enemy.Enable()
        for m in self.missile_images:
            if m.enabled:
                m.quad.Enable()
        self.enemy.locked = False
        self.fill_state()
        #The enemy is not locked so remove the line we just calculated
        self.reset_line(Objects.ENEMY)
        for obj_type in Objects.mobile:
            for i in xrange(0, len(self.future_state)):
                try:
                    self.future_state[i][1][obj_type].line_seg.Enable()
                except KeyError:
                    continue
            #Also the saved segs
            if obj_type not in self.saved_segs:
                continue
            for (t,line_seg) in self.saved_segs[obj_type]:
                line_seg.Enable()
        #Finally the firing solution line
        for body in self.firing_solution_steps:
            body.line_seg.Enable()
        self.fire_button.disarm()
        self.last = globals.time

    def fire(self):
        if self.stopped:
            #hack, this works the menu
            self.menu.choose()
            return
        if self.tutorial == self.tutorial_fire:
            self.tutorial()
        if self.arming_weapon == 3: #chaff
            self.fire_button.disarm()
            self.arm_progress.SetBarLevel(0)
            self.start_explosion( self.initial_state[Objects.PLAYER].pos, radius=self.explosion_radius*1.4, colour = (0.2,0.2,1) )
            #If any missiles are in our radius then we'll just make them inert
            for obj_type in Objects.missiles:
                try:
                    p = self.initial_state[obj_type].pos
                except KeyError:
                    continue
                diff = (p - self.initial_state[Objects.PLAYER].pos).length()
                if diff < self.explosion_radius*1.5:
                    #Kill this missile
                    self.destroy_missile(obj_type,explode=False)
            return

        if self.firing_solution is None:
            self.console.add_text('Need firing solution')
            return
        radius = self.explosion_radius
        if self.arming_weapon == 2:
            radius *= 3
        self.console.add_text('%s launched' % self.weapon_names[self.arming_weapon])
        globals.sounds.fire.play()
        if self.arming_weapon == 2:
            globals.sounds.voice_nuke_launch.play()
        elif self.arming_weapon == 1:
            globals.sounds.voice_probe_launch.play()
        self.launch_missile( Objects.PLAYER, *self.firing_solution, radius=radius, probe=self.arming_weapon == 1 )
        self.fire_button.disarm()
        self.arm_progress.SetBarLevel(0)

    def thrust(self, on, key):
        if not self.thrusters:
            return
        if self.stopped:
            #quick hack, this works the menu while stopped
            if not on:
                self.menu.key_press(key)
            return
        if on:
            self.mode.KeyDown(key)
        else:
            self.mode.KeyUp(key)

    def keypad_pressed(self, n):

        if not self.console.entering or self.stopped:
            return
        globals.sounds.keypad.play()
        if n == 'E':
            self.console.add_char('\n')
            text = ''.join(self.keypad.buffer)
            self.keypad.buffer = []
            if self.console.entering == 1:
                try:
                    manual_bearing = float(text) % 360.0
                except ValueError:
                    self.console.add_text('Invalid')
                    return
                self.bearing_text.SetText('%05.1f' % manual_bearing)
                self.manual_bearing = math.pi * (manual_bearing / 180.0)
                self.console.add_text('Enter fuse time:')
                self.console.entering = 2
            else:
                try:
                    timer = float(text) % 30.0
                except ValueError:
                    self.console.add_text('Invalid')
                    return

                self.console.add_text('Solution acquired')
                self.console.entering = False
                self.set_firing_solution(self.manual_bearing, timer*globals.tick_factor, reacquire=False, manual=True)


        else:
            self.console.add_char(n)
            self.keypad.buffer.append(n)

    def fill_state(self):
        try:
            current,state = self.future_state[-1]
        except IndexError:
            current = globals.time
            state = self.initial_state
        t = current + self.step_time
        period = 20000.0

        while t < globals.time + period:
            next_state = { Objects.SUN  : self.sun_body }
            for obj_type in Objects.mobile:
                try:
                    obj = state[obj_type].step(self.step_time * globals.time_factor, self.fixed_bodies)
                except KeyError:
                    continue
                next_state[obj_type] = obj

            self.future_state.append( (t, next_state) )
            t += self.step_time
            state = next_state

        for obj_type in Objects.mobile:
            #Hack to not draw the first line segment which is behind us
            for i in xrange(0, len(self.future_state)):
                intensity = 1^(i&1)# - ((self.future_state[i][0] - self.future_state[0][0])/period)
                try:
                    if obj_type in line_colours and (obj_type != Objects.ENEMY or self.enemy.locked):
                        col = line_colours[obj_type] + (intensity, )
                        self.future_state[i][1][obj_type].line_seg.SetColour( col )
                    else:
                        self.future_state[i][1][obj_type].line_seg.Disable()
                except KeyError:
                    pass

    def fill_state_obj(self, obj_type):
        if obj_type == Objects.ENEMY and not self.enemy.locked:
            return
        last = self.initial_state[obj_type]
        for t, state in self.future_state:
            if obj_type not in state:
                n = last.step(self.step_time * globals.time_factor, self.fixed_bodies)
                state[obj_type] = n
            last = state[obj_type]

        for i in xrange(0, len(self.future_state)):
            intensity = 1^(i&1)# - ((self.future_state[i][0] - self.future_state[0][0])/period)
            try:
                if obj_type in line_colours and (obj_type != Objects.ENEMY or self.enemy.locked):
                    col = line_colours[obj_type] + (intensity, )
                    self.future_state[i][1][obj_type].line_seg.SetColour( col )
                else:
                    self.future_state[i][1][obj_type].line_seg.Disable()
            except KeyError:
                pass

    def StartMusic(self):
        pygame.mixer.music.play(-1)
        pygame.mixer.music.set_volume(0.2)
        self.music_playing = True

    def Draw(self):
        drawing.ResetState()

        #drawing.Translate(-400,-400,0)
        s = 1.0
        #drawing.Scale(s,s,1)
        #drawing.Translate(-self.viewpos.pos.x/s,-self.viewpos.pos.y/s,0)
        drawing.ResetState()
        drawing.Scale(self.zoom,self.zoom,1)
        drawing.Translate(-self.viewpos.pos.x,-self.viewpos.pos.y,0)

        drawing.LineWidth(8)
        drawing.DrawNoTexture(self.explosion_line_buffer)
        drawing.LineWidth(2)
        drawing.DrawNoTexture(globals.line_buffer)

        drawing.DrawAll(globals.quad_buffer,self.atlas.texture)
        drawing.DrawAll(globals.nonstatic_text_buffer,globals.text_manager.atlas.texture)

    def DrawFinal(self):
        drawing.DrawNoTexture(globals.colour_tiles)

    def get_obj_at_time(self, obj_type, target):
        #Get the first one before it
        closest_before = None
        closest_after = None
        for i, (t, state) in enumerate(self.future_state):
            if t < target:
                try:
                    closest_before = state[obj_type]
                except KeyError:
                    pass
            if t > target:
                try:
                    closest_after = state[obj_type]
                except KeyError:
                    pass
                break

        if closest_before is None:
            guess = closest_after
        elif closest_after is None:
            guess = closest_before
        else:
            #could interpolate, for now just pick one
            guess = closest_before
        return guess

    def Update(self,t):
        if self.mode:
            self.mode.Update(t)

        if self.stopped:
            return

        if self.end_time and (globals.time - self.end_time) > 1000:
            self.Stop()
            if self.player_health <= 0:
                self.menu.show_die_screen()
            else:
                self.menu.show_win_screen()

        self.echoes = [echo for echo in self.echoes if echo.update()]

        if self.disabled and globals.time > self.finish_stabalising:
            self.disabled = False
            self.overlay.SetColour( self.no_overlay )
            self.stabalise_orbit(Objects.PLAYER)
            globals.sounds.power_up.play()

        if self.arm_end is not None:
            if globals.time > self.arm_end:
                self.console.add_text('Armed %s' % self.weapon_names[self.arming_weapon])
                if self.tutorial == self.tutorial_arm and self.selected_weapon == 0:
                    self.tutorial()
                self.arm_end = None
                self.fire_button.arm()
            else:
                partial = float(globals.time - self.arm_start)/self.arm_duration
                self.arm_progress.SetBarLevel(partial)

        #kill missiles in flight
        to_destroy = []
        for obj_type, (t, r, probe) in self.detonation_times.iteritems():
            if t < globals.time:
                to_destroy.append((obj_type, r, probe))
        for (obj_type,r,probe) in to_destroy:
            self.destroy_missile(obj_type, radius=r, probe=probe)

        #The missiles could have killed someone
        if self.stopped:
            return

        #draw explosions
        if self.explosions:
            new_explosions = []
            for exp in self.explosions:
                if exp.Update():
                    new_explosions.append(exp)
            self.explosions = new_explosions

        if self.firing_solution and (globals.time - self.firing_solution_time) > 500 and self.enemy.locked:
            #reacquire
            self.lock_on(self.enemy, reacquire=True)

        self.console.update()

        line_update = False
        if self.last is None:
            self.last = globals.time
        else:
            elapsed = globals.time - self.last
            self.last = globals.time
            for obj_type in Objects.mobile:
                if obj_type not in self.initial_state:
                    continue
                # try:
                #     target_type,force = self.powered[obj_type]
                #     target = self.initial_state[target_type].pos

                # except:
                #     pass
                if obj_type == Objects.PLAYER and not self.disabled:
                    #cheat as the sun is at 0,0
                    body = self.initial_state[obj_type]
                    to_sun = body.pos.unit_vector()
                    parallel = to_sun.Rotate(math.pi*0.25)
                    move_force = (to_sun*self.move_direction.y + parallel *self.move_direction.x) * 20 * globals.time_factor

                    body.set_force(move_force)
                    line_update = True

                n = self.initial_state[obj_type].step(elapsed * globals.time_factor, self.fixed_bodies, line = False)
                if obj_type == Objects.PLAYER and self.firing_solution is not None:
                    #Draw the current firing soltion
                    self.clear_firing_solution_steps()
                    v = cmath.rect(self.missile_speed, self.firing_solution[0])
                    velocity = Point(v.real, v.imag)
                    body = self.initial_state[obj_type]
                    body = Body( body.pos, body.velocity + velocity, Objects.MISSILE1, Missile.mass )
                    for i in xrange(5):
                        body = body.step(2000 * globals.time_factor, self.fixed_bodies)
                        self.firing_solution_steps.append(body)
                if (obj_type == Objects.ENEMY and not self.enemy.locked):
                    self.object_quads[obj_type].Disable()
                else:
                    self.object_quads[obj_type].set_vertices( n.pos )
                    self.object_quads[obj_type].Enable()
                self.initial_state[obj_type] = n

        if line_update:
            self.initial_state[Objects.PLAYER].set_force(Point(0,0))
            self.reset_line( Objects.PLAYER, saved_segs=False)

        if self.enemy.locked:
            distance = (self.initial_state[Objects.PLAYER].pos - self.initial_state[Objects.ENEMY].pos).length()
            lock_age = globals.time - self.lock_time
            if distance > self.scan_radius*1.4 and lock_age > 10000:
                self.lose_lock(self.enemy)


        if self.scan_start:
            partial = globals.time - self.scan_start
            if partial > self.scan_duration:
                self.end_scan(self)
            else:
                self.draw_scan( self.scan_radius, self.scan_start_pos, self.scan_lines, partial / self.scan_duration )

        if self.enemy.scan_start:
            partial = globals.time - self.enemy.scan_start
            if partial > self.scan_duration:
                self.end_scan(self.enemy)
                distance = (self.initial_state[Objects.PLAYER].pos - self.initial_state[Objects.ENEMY].pos).length()
                if distance < self.scan_radius:
                    self.enemy.has_lock = True
                    self.enemy.lock_time = globals.time
                else:
                    self.enemy.has_lock = False
                    self.enemy.lock_time = None
            else:
                self.draw_scan( self.enemy.scan_radius,
                                self.enemy.scan_start_pos,
                                self.enemy.scan_lines,
                                partial / self.enemy.scan_duration )

        if self.future_state[1][0] < globals.time:
            #Now there's been an update, let's see if we can get a firing solution on the player :)
            if self.enemy.active and self.enemy_health > 0:
                #If the enemy does not have a lock it needs to try and get one
                if not self.enemy.has_lock:
                    if self.enemy.scan_start is None:
                        #if we don't have a lock we must scan
                        self.enemy.scan_start = globals.time
                        globals.sounds.scan.play()
                        self.enemy.scan_end = globals.time + self.scan_duration
                        self.enemy.scan_start_pos = self.initial_state[Objects.ENEMY].pos
                    else:
                        #it's ok, we're scanning
                        pass
                else:
                    #the enemy has a lock, but has it expired?
                    lock_age = globals.time - self.enemy.lock_time
                    distance = (self.initial_state[Objects.PLAYER].pos - self.initial_state[Objects.ENEMY].pos).length()
                    if distance > self.scan_radius*1.4 and lock_age > 10000:
                        self.enemy.has_lock = False
                    else:
                        #The lock is still live. Maybe fire
                        if self.enemy.last_launch is None or (globals.time - self.enemy.last_launch) > 2500:
                            solution = self.initial_state[Objects.ENEMY].scan_for_target( self.initial_state[Objects.PLAYER], self.explosion_radius )
                            if solution is not None:
                                self.console.add_text('Enemy launch detected')
                                if not globals.played_launch:
                                    globals.sounds.voice_enemy_launch.play()
                                    globals.played_launch = True
                                self.launch_missile( Objects.ENEMY, *solution )
                                self.enemy.last_launch = globals.time

            #Kill the line segments that are in the future
            for t,state in self.future_state:
                for obj_type in Objects.mobile:
                    if obj_type not in state:
                        continue
                    if t > globals.time:
                        state[obj_type].line_seg.Delete()
                    else:
                        #For the others store them for later deletion
                        intensity = 1
                        try:
                            col = line_colours[obj_type] + (intensity, )
                        except:
                            continue
                        state[obj_type].line_seg.SetColour( col )
                        self.saved_segs[obj_type].append( (t, state[obj_type].line_seg ) )

            self.future_state = []
            self.fill_state()


        for obj_type in Objects.mobile:
            new_saved = []
            trail_age, trail_fade = self.trail_properties[obj_type]
            if obj_type not in self.saved_segs:
                continue
            for (t,line_seg) in self.saved_segs[obj_type]:
                age = globals.time - t
                if age < trail_age:
                    new_saved.append( (t,line_seg) )
                elif age > trail_age + trail_fade:
                    line_seg.Delete()
                else:
                    intensity = 1 - ((age - trail_age) / trail_fade)
                    col = line_colours[obj_type] + (intensity, )
                    line_seg.SetColour( col )
                    new_saved.append( (t,line_seg) )
            self.saved_segs[obj_type] = new_saved

        if self.game_over:
            return

    def reset_line(self, obj_type, saved_segs=True):
        for t, state in self.future_state:
            if obj_type in state:
                state[obj_type].line_seg.Delete()
        for t, state in self.future_state:
            if obj_type in state:
                del state[obj_type]

        if saved_segs:
            for (t,line_seg) in self.saved_segs[obj_type]:
                line_seg.Delete()
            self.saved_segs[obj_type] = []

        self.fill_state_obj(obj_type)

    def arm_weapon(self):
        globals.sounds.keypad.play()
        if self.selected_weapon is None:
            self.console.add_text('No weapon selected')
            return

        self.arm_start = globals.time
        self.arm_duration = self.weapon_arm_times[self.selected_weapon]
        self.arm_end = globals.time + self.arm_duration
        self.arming_weapon = self.selected_weapon
        self.fire_button.disarm()
        self.arm_progress.SetBarLevel(0)
        self.console.add_text('Arming...')

    def select_weapon(self, state, index):
        if self.stopped:
            #don't care
            return

        if not state:
            self.selected_weapon = None
            return

        if self.selected_weapon is not None and self.selected_weapon != index:
            if self.weapon_buttons[self.selected_weapon].state:
                self.weapon_buttons[self.selected_weapon].OnClick(None,None,skip_callback=True)

        self.selected_weapon = index

    def launch_missile(self, source_type, angle, delay, radius = None, probe=False):
        #find a new id for the missile
        if radius is None:
            radius = self.explosion_radius
        for obj_type in Objects.missiles:
            if obj_type not in self.initial_state:
                #found one
                break
        else:
            return
        source = self.initial_state[source_type]
        v = cmath.rect(self.missile_speed, angle)
        velocity = Point(v.real, v.imag)
        self.initial_state[obj_type] = Body( source.pos, source.velocity + velocity, obj_type, Missile.mass )
        self.detonation_times[obj_type] = (globals.time + delay, radius, probe)

    def destroy_missile(self, obj_type, already_exploding=None, radius=None, explode=True, probe=False):
        #remove it from the initial_state
        if already_exploding is None:
            already_exploding = set()
        if probe and explode:
            self.scan_start = globals.time
            self.scan_end = globals.time + self.scan_duration
            self.scan_start_pos = self.initial_state[obj_type].pos
            globals.sounds.scan.play()
        elif explode:
            if radius is None:
                radius = self.explosion_radius
            self.start_explosion( self.initial_state[obj_type].pos, radius )
            #check for damage
            if radius == self.explosion_radius:
                globals.sounds.explode.play()
            else:
                globals.sounds.nuke.play()
            for obj in Objects.mobile:
                if obj == obj_type:
                    continue
                try:
                    p = self.initial_state[obj].pos
                except KeyError:
                    continue

                diff = (p - self.initial_state[obj_type].pos).length()
                if diff < radius:
                    #damage
                    if obj >= Objects.MISSILE1:
                        if obj not in already_exploding:
                            already_exploding.add(obj_type)
                            self.destroy_missile(obj,already_exploding=already_exploding,explode=True)
                    else:
                        damage = 100 if radius == self.explosion_radius else 1000
                        self.damage(obj, damage * (1 - (diff / radius)))
        del self.initial_state[obj_type]
        del self.detonation_times[obj_type]
        for t,state in self.future_state:
            if obj_type in state:
                state[obj_type].line_seg.Delete()
                del state[obj_type]
        self.object_quads[obj_type].Disable()
        if obj_type in self.saved_segs:
            for (t,seg) in self.saved_segs[obj_type]:
                seg.Delete()
            self.saved_segs[obj_type] = []

    def damage(self, obj, amount):
        if obj == Objects.PLAYER:
            self.console.add_text('Damage detected')
            self.player_health -= amount
            if self.player_health <= 0:
                if self.end_time is None:
                    self.end_time = globals.time
        else:
            self.enemy_health -= amount
            self.console.add_text('Enemy damaged')
            if self.enemy_health <= 0:
                if self.end_time is None:
                    self.lose_lock(self.enemy)
                    self.end_time = globals.time

    def start_explosion(self, p, radius=None, colour=(1,1,1)):
        start = globals.time
        end = globals.time + self.explosion_duration
        pos = p
        if radius is None:
            radius = self.explosion_radius
        self.explosions.append( Explosion(self.explosion_line_buffer, start, end, pos, radius, colour) )

    def hit_stabalise(self):
        if self.stopped:
            return
        self.finish_stabalising = globals.time + self.stabalise_duration
        self.disabled = True
        globals.sounds.power_down.play()
        globals.sounds.voice_stabalising.play()
        if self.enemy.locked:
            self.lose_lock(self.enemy)

        self.overlay.SetColour(self.disabled_colour)

    def stabalise_orbit(self, obj_type):
        body = self.initial_state[obj_type]
        r = body.pos.length()
        #Which direction? We want the component of the current velocity in the direction of the radius tangent
        tangent = body.pos.unit_vector().Rotate(math.pi/2)

        dot = (tangent * body.velocity)
        dot = dot.x + dot.y

        if dot > 0:
            mul = 1
        else:
            mul = -1

        body.velocity = tangent * (math.sqrt(G * self.sun_body.mass / (r * globals.pixels_to_units))) * mul

    def start_scan(self):
        #The player has started a scan, start drawing the circle
        if self.disabled or self.stopped:
            return
        globals.sounds.scan.play()
        self.scan_start = globals.time
        self.scan_end = globals.time + self.scan_duration
        self.scan_start_pos = self.initial_state[Objects.PLAYER].pos

    def draw_scan(self, scan_radius, scan_start_pos, scan_lines, partial):
        r = scan_radius * partial
        angles = [i*math.pi*2/self.scan_line_parts for i in xrange(self.scan_line_parts)]
        v = cmath.rect(r, angles[0])
        last = scan_start_pos + Point(v.real, v.imag)
        for i in xrange(self.scan_line_parts):
            angle = angles[(i + 1) % len(angles)]
            v = cmath.rect(r, angle)
            p = scan_start_pos + Point(v.real, v.imag)
            if not self.enemy.locked or (not self.manual_button.state and not self.firing_solution):
                d = (p - self.initial_state[Objects.ENEMY].pos).SquareLength()
                #mega hax
                if d < 1000 and scan_lines is self.scan_lines:
                    self.lock_on(self.enemy)

            scan_lines[i].SetVertices( last, p, 10000 )
            last = p
            intensity = 1 - partial
            scan_lines[i].SetColour( (1,1,0.4,intensity))

    def end_scan(self, body):
        body.scan_start = None
        for line in body.scan_lines:
            line.SetColour( (0,0,0,0) )
        if body is self and not self.enemy.locked:
            self.echoes.append(Echo(self.initial_state[Objects.ENEMY].pos, globals.time))

    def lock_on(self, enemy, reacquire=False):
        if self.enemy_health <= 0:
            return
        enemy.locked = True
        if not reacquire:
            self.lock_time = globals.time
        if self.manual_button.state:
            return
        if self.tutorial == self.tutorial_click_scan:
            self.tutorial()
        #Let's try and grab a firing solution
        solution = self.initial_state[Objects.PLAYER].scan_for_target( self.initial_state[Objects.ENEMY], self.explosion_radius )
        if solution is None:
            return
        self.set_firing_solution( *solution, reacquire=reacquire )

    def lose_lock(self, enemy):
        enemy.locked = False
        self.lock_time = None
        if self.firing_solution and not self.manual_button.state:
            self.clear_firing_solution()
        self.reset_line(Objects.ENEMY)
        self.console.add_text('Target lost')
        globals.sounds.target_lost.play()

    def clear_firing_solution(self):
        #Draw the current firing soltion
        self.firing_solution = None
        self.clear_firing_solution_steps()
        self.bearing_text.SetText('---.-')
        self.fuse_text.SetText('---.-')

    def clear_firing_solution_steps(self):
        for body in self.firing_solution_steps:
            body.line_seg.Delete()
        self.firing_solution_steps = []

    def set_firing_solution(self, angle, delay, reacquire=False, manual=False):
        self.clear_firing_solution()
        self.firing_solution_time = globals.time
        if not manual and not reacquire:
            self.console.add_text('Target Locked')
            globals.sounds.target_locked.play()

        self.firing_solution = (angle, delay)
        angle_degrees = 180*angle/math.pi
        self.bearing_text.SetText('%05.1f' % angle_degrees)
        delay_seconds = delay/globals.tick_factor
        self.fuse_text.SetText('%05.1f' % delay_seconds)

        #self.launch_missile( Objects.PLAYER, angle, delay )

    def manual_firing(self, state):
        if self.stopped:
            return
        if self.console.entering:
            self.console.entering = False
            self.console.add_text('\ncancelled')
            return

        if not state:
            self.clear_firing_solution()
            return
        self.console.add_text('Enter bearing:')
        self.console.entering = 1
        self.keypad.buffer = []

    def GameOver(self):
        self.game_over = True
        self.mode = modes.GameOver(self)


    def MouseButtonDown(self,pos,button):
        screen_pos = self.viewpos.Get() + (pos/self.zoom)

        #Hax!
        if self.tutorial == self.tutorial_click_screen:
            if pos.x >= 25 and pos.x <= 117 and pos.y >= 27 and pos.y <= 77:
                self.tutorial()
                return True,None

        handled,dragging = super(GameView,self).MouseButtonDown(screen_pos,button)

        if handled or self.stopped:
            return handled,dragging
        if button == 1:
            self.zooming = None
            self.dragging = screen_pos
            return True,self
        if button == 2:
            self.dragging = None
            self.zooming = screen_pos
            return True,self

        return False,None

    def IsDragging(self):
        return True if self.dragging else False

    def MouseButtonUp(self,pos,button):
        screen_pos = self.viewpos.Get() + (pos/self.zoom)

        handled,dragging = super(GameView,self).MouseButtonUp(screen_pos,button)
        if handled:
            return handled,dragging

        if button == 1:
            self.dragging = None
            return True,False
        if button == 2:
            self.zooming = None
            return True,False
        if not self.zooming and not globals.dragging:
            if button == 4:
                self.AdjustZoom(-0.5,pos)
            elif button == 5:
                self.AdjustZoom(+0.5,pos)

        return False,self.IsDragging()

    def MouseMotion(self,pos,rel,handled):
        screen_pos = self.viewpos.Get() + (pos/self.zoom)
        screen_rel = rel/self.zoom
        self.mouse_pos = pos

        handled = super(GameView,self).MouseMotion(screen_pos,screen_rel,handled)
        if handled:
            return handled
        #always do dragging
        if self.dragging:
            self.viewpos.Set(self.dragging - (pos/self.zoom))
            self.ClampViewpos()
            self.dragging = self.viewpos.Get() + (pos/self.zoom)
            if self.tutorial == self.tutorial_drag:
                self.tutorial()
        elif self.zooming:
            self.AdjustZoom(-rel.y/100.0,globals.screen/2)

    def AdjustZoom(self,amount,pos):
        #hack to get the zooming right
        if self.stopped:
            return
        pos -= Point(320,180)
        pos_coords = self.viewpos.Get() + (pos/self.zoom)
        oldzoom = self.zoom

        self.zoom -= (amount/10.0)
        if self.zoom > 3:
            self.zoom = 3
        if self.zoom < 0.3:
            self.zoom = 0.3


        #if we've zoomed so far out that we can see an edge of the screen, fix that
        top_left= Point(0,globals.screen.y/self.zoom)
        top_right = globals.screen/self.zoom
        bottom_right = Point(globals.screen.x/self.zoom,0)

        new_viewpos = self.viewpos.Get()
        x = self.absolute.size.x - (globals.screen.x/self.zoom)
        y = self.absolute.size.y - (globals.screen.y/self.zoom)
        if new_viewpos.y < -y:
            new_viewpos.y = -y

        if new_viewpos.x < -x:
            new_viewpos.x = -x

        #now the top left
        new_top_right = new_viewpos+top_right
        if new_top_right.y  > self.absolute.size.y:
            new_viewpos.y -= (new_top_right.y - self.absolute.size.y)

        if new_top_right.x > self.absolute.size.x:
            new_viewpos.x -= (new_top_right.x - self.absolute.size.x)

        try:
            if new_viewpos.y < -y:
                raise ValueError

            if new_viewpos.x < -x:
                raise ValueError

            #now the top left
            new_top_right = new_viewpos+top_right
            if new_top_right.y  > self.absolute.size.y:
                raise ValueError

            if new_top_right.x > self.absolute.size.x:
                raise ValueError

        except ValueError:
            #abort! This is a bit shit but whatever
            self.zoom = oldzoom
            return

        new_pos_coords = self.viewpos.Get() + pos/self.zoom
        a = self.viewpos.Get() + (pos_coords - new_pos_coords)
        if a.x < -x or a.x > x or a.y < -y or a.y > y:
            self.zoom = oldzoom
            return
        self.viewpos.Set(a)

    def ClampViewpos(self):
        #print self.viewpos.pos,self.absolute.size.x - (globals.screen.x/self.zoom)
        #return
        x = self.absolute.size.x - (globals.screen.x/self.zoom)
        y = self.absolute.size.y - (globals.screen.y/self.zoom)
        if self.viewpos.pos.x < -x:
            self.viewpos.pos.x = -x
        if self.viewpos.pos.y < -y:
            self.viewpos.pos.y = -y
        if self.viewpos.pos.x > x:
            self.viewpos.pos.x = x
        if self.viewpos.pos.y > y:
            self.viewpos.pos.y = y

    def KeyDown(self,key):
        if self.stopped:
            return
        if key in self.key_to_thrust:
            self.key_to_thrust[key].Depress(None)

    def KeyUp(self,key):
        if key == pygame.K_DELETE:
            if self.music_playing:
                self.music_playing = False
                pygame.mixer.music.set_volume(0)
            else:
                self.music_playing = True
                pygame.mixer.music.set_volume(0.2)
        if key == pygame.K_ESCAPE:
            self.Stop()
        if self.stopped:
            return
        if key in self.key_to_thrust:
            self.key_to_thrust[key].Undepress()

        #self.mode.KeyUp(key)

