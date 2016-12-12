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
        for angle in angle_guesses:
            body = self
            v = cmath.rect(globals.game_view.missile_speed, angle)
            velocity = Point(v.real, v.imag)
            body = Body(body.pos, body.velocity + velocity, body.type, body.mass)
            step = 1000
            t = globals.time

            while t < globals.time + period:
                target = globals.game_view.get_obj_at_time( target.type, t )
                if target:
                    distance = (target.pos - body.pos).length()
                    if distance < min_distance and (t - globals.time) < best_time:
                        best_time = t - globals.time
                        firing_angle = angle
                    #body.apply_force_towards( target, 1 )
                body = body.step(step * globals.time_factor, globals.game_view.fixed_bodies, line = False)
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
    def __init__(self, *args, **kwargs):
        super(Enemy, self).__init__(*args, **kwargs)
        self.locked = False
        #Inert like an asteroid
        self.active = False

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
    mobile = [PLAYER, ENEMY] + missiles

line_colours = { Objects.PLAYER : (0,0,1),
                 Objects.MISSILE1 : (0.2,0.2,0.2),
                 Objects.ENEMY  : (1,0,0) }

for t in Objects.missiles:
    line_colours[t] = line_colours[Objects.MISSILE1]

class Explosion(object):
    line_segs = 32
    def __init__(self, line_buffer, start, end, pos, radius):
        self.lines = [drawing.Line(line_buffer) for i in xrange(self.line_segs)]
        self.start = start
        self.radius = radius
        self.end = end
        self.duration = float(end - start)
        self.pos = pos

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
            self.lines[i].SetColour( (1,1,1,intensity))
        if globals.time > self.end:
            for line in self.lines:
                line.Delete()
            return False
        return True

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
    explosion_radius = 20
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
        #pygame.mixer.music.load('music.ogg')
        #self.music_playing = False
        super(GameView,self).__init__(Point(0,0),globals.screen*4)
        #self.square = drawing.Line(globals.line_buffer)
        #self.square.SetVertices( Point(0,0), Point(1000,1000), 1000)
        #self.square.SetColour( (1,0,0,1) )
        self.explosion_line_buffer = drawing.LineBuffer(32*Explosion.line_segs)
        self.sun = Sun()
        self.ship = Ship()
        self.enemy = Enemy()
        self.grid = ui.Grid(self,Point(-1,-1),Point(1,1),Point(40,40))
        self.grid.Enable()
        self.sun_body  = FixedBody( pos=Point(0,0), velocity=Point(0,0), type=Objects.SUN, mass=100000000 )
        self.sun.set_vertices(self.sun_body.pos)
        orbit_velocity = (math.sqrt(G * self.sun_body.mass / (100 * globals.pixels_to_units)))
        #orbit_velocity = 3
        print orbit_velocity

        self.ship_body = Body( Point(100, 0), (Point(0,-1).unit_vector()) * orbit_velocity, type=Objects.PLAYER, mass=1 )
        self.enemy_body = Body( Point(120, 120), (Point(1,-1).unit_vector()) * 100, type=Objects.ENEMY, mass=1 )

        self.fixed_bodies = [self.sun_body]
        self.missile_images = [Missile() for i in xrange(5)]
        self.initial_state = { Objects.PLAYER : self.ship_body,
                               Objects.ENEMY  : self.enemy_body,
                               Objects.SUN    : self.sun_body }
        self.object_quads = { Objects.PLAYER : self.ship,
                              Objects.ENEMY : self.enemy,
                              Objects.MISSILE1 : self.missile_images[0],
                              Objects.MISSILE2 : self.missile_images[1],
                              Objects.MISSILE3 : self.missile_images[2],
                              Objects.MISSILE4 : self.missile_images[3],
                              Objects.MISSILE5 : self.missile_images[4],
                              }
        self.trail_properties = { Objects.PLAYER : (60000.0, 8000.0),
                                  Objects.ENEMY  : (60000.0, 8000.0) }
        for t in Objects.missiles:
            self.trail_properties[t] = (0,400.0)

        self.scan_lines = [drawing.Line(globals.line_buffer) for i in xrange(self.scan_line_parts)]
        #set up the state
        self.future_state = []
        self.fill_state()
        #skip titles for development of the main game
        #self.mode = modes.Titles(self)
        self.viewpos = Viewpos(Point(-320,-180))
        self.dragging = None
        self.zoom = 1
        self.zooming = None
        self.temp_bodies = []
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


        self.manual_button = ui.ImageBoxToggleButton(globals.screen_root,
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

    def fire(self):
        if self.firing_solution is None:
            self.console.add_text('Need firing solution')
            return
        print 'fire!'

    def thrust(self, on, key):
        if on:
            self.mode.KeyDown(key)
        else:
            self.mode.KeyUp(key)

        #print 'thrust',on,key


    def keypad_pressed(self, n):
        #print 'kp',n
        if not self.console.entering:
            return

        if n == 'E':
            self.console.add_char('\n')
            text = ''.join(self.keypad.buffer)
            print 'enter',text
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
        pass
        #pygame.mixer.music.play(-1)
        #self.music_playing = True

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

        #drawing.DrawAll(globals.nonstatic_text_buffer,globals.text_manager.atlas.texture)

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

        if self.disabled and globals.time > self.finish_stabalising:
            self.disabled = False
            self.overlay.SetColour( self.no_overlay )
            self.stabalise_orbit(Objects.PLAYER)

        if self.arm_end is not None:
            if globals.time > self.arm_end:
                self.console.add_text('Armed %s' % self.weapon_names[self.arming_weapon])
                self.arm_end = None
                self.fire_button.arm()
            else:
                partial = float(globals.time - self.arm_start)/self.arm_duration
                self.arm_progress.SetBarLevel(partial)

        #kill missiles in flight
        to_destroy = []
        for obj_type, t in self.detonation_times.iteritems():
            if t < globals.time:
                to_destroy.append(obj_type)
        for obj_type in to_destroy:
            self.destroy_missile(obj_type)

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
                    self.object_quads[obj_type].quad.Disable()
                else:
                    self.object_quads[obj_type].set_vertices( n.pos )
                    self.object_quads[obj_type].quad.Enable()
                self.initial_state[obj_type] = n

        if line_update:
            self.initial_state[Objects.PLAYER].set_force(Point(0,0))
            self.reset_line( Objects.PLAYER, saved_segs=False)

        if self.enemy.locked:
            distance = (self.initial_state[Objects.PLAYER].pos - self.initial_state[Objects.ENEMY].pos).length()
            if distance > self.scan_radius*1.4:
                self.lose_lock(self.enemy)


        if self.scan_start:
            partial = globals.time - self.scan_start
            if partial > self.scan_duration:
                self.end_scan()
            else:
                self.draw_scan( partial / self.scan_duration )

        if self.future_state[1][0] < globals.time:
            #Now there's been an update, let's see if we can get a firing solution on the player :)
            if self.enemy.active:
                solution = self.initial_state[Objects.ENEMY].scan_for_target( self.initial_state[Objects.PLAYER], self.explosion_radius )
                if solution is not None:
                    print 'Enemy has firing solution go go go',solution
                    self.launch_missile( Objects.ENEMY, *solution )
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
        if not state:
            #don't care
            return

        if self.selected_weapon is not None and self.selected_weapon != index:
            if self.weapon_buttons[self.selected_weapon].state:
                self.weapon_buttons[self.selected_weapon].OnClick(None,None,skip_callback=True)

        self.selected_weapon = index

    def launch_missile(self, source_type, angle, delay):
        #find a new id for the missile
        for obj_type in Objects.missiles:
            if obj_type not in self.initial_state:
                #found one
                break
        else:
            print 'gah couldn\'t find space for a new missile'
            return
        print 'new missile is',obj_type
        source = self.initial_state[source_type]
        v = cmath.rect(self.missile_speed, angle)
        velocity = Point(v.real, v.imag)
        self.initial_state[obj_type] = Body( source.pos, source.velocity + velocity, obj_type, Missile.mass )
        self.detonation_times[obj_type] = globals.time + delay

    def destroy_missile(self, obj_type):
        #remove it from the initial_state
        self.start_explosion( self.initial_state[obj_type].pos )
        del self.initial_state[obj_type]
        del self.detonation_times[obj_type]
        for t,state in self.future_state:
            if obj_type in state:
                state[obj_type].line_seg.Delete()
            del state[obj_type]
        self.object_quads[obj_type].quad.Disable()
        if obj_type in self.saved_segs:
            for (t,seg) in self.saved_segs[obj_type]:
                seg.Delete()
            self.saved_segs[obj_type] = []

    def start_explosion(self, p):
        start = globals.time
        end = globals.time + self.explosion_duration
        pos = p
        self.explosions.append( Explosion(self.explosion_line_buffer, start, end, pos, self.explosion_radius) )

    def hit_stabalise(self):
        self.finish_stabalising = globals.time + self.stabalise_duration
        self.disabled = True
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
        print dot,mul

        body.velocity = tangent * (math.sqrt(G * self.sun_body.mass / (r * globals.pixels_to_units))) * mul

    def start_scan(self):
        #The player has started a scan, start drawing the circle
        if self.disabled:
            return
        self.scan_start = globals.time
        self.scan_end = globals.time + self.scan_duration
        self.scan_start_pos = self.initial_state[Objects.PLAYER].pos

    def draw_scan(self, partial):
        r = self.scan_radius * partial
        angles = [i*math.pi*2/self.scan_line_parts for i in xrange(self.scan_line_parts)]
        v = cmath.rect(r, angles[0])
        last = self.scan_start_pos + Point(v.real, v.imag)
        for i in xrange(self.scan_line_parts):
            angle = angles[(i + 1) % len(angles)]
            v = cmath.rect(r, angle)
            p = self.scan_start_pos + Point(v.real, v.imag)
            if not self.enemy.locked or (not self.manual_button.state and not self.firing_solution):
                d = (p - self.initial_state[Objects.ENEMY].pos).SquareLength()
                if d < 1000:
                    self.lock_on(self.enemy)

            self.scan_lines[i].SetVertices( last, p, 10000 )
            last = p
            intensity = 1 - partial
            self.scan_lines[i].SetColour( (1,1,0.4,intensity))


    def end_scan(self):
        self.scan_start = None
        for line in self.scan_lines:
            line.SetColour( (0,0,0,0) )

    def lock_on(self, enemy, reacquire=False):
        enemy.locked = True
        if self.manual_button.state:
            return
        #Let's try and grab a firing solution
        solution = self.initial_state[Objects.PLAYER].scan_for_target( self.initial_state[Objects.ENEMY], self.explosion_radius )
        if solution is None:
            print 'Error grabbing solution'
            return
        self.set_firing_solution( *solution, reacquire=reacquire )

    def lose_lock(self, enemy):
        enemy.locked = False
        if self.firing_solution and not self.manual_button.state:
            self.clear_firing_solution()
        self.reset_line(Objects.ENEMY)
        self.console.add_text('Target lost')

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
        print 'set firing solution', angle, delay
        self.clear_firing_solution()
        self.firing_solution_time = globals.time
        if not manual and not reacquire:
            self.console.add_text('Target Locked')

        self.firing_solution = (angle, delay)
        angle_degrees = 180*angle/math.pi
        self.bearing_text.SetText('%05.1f' % angle_degrees)
        delay_seconds = delay/globals.tick_factor
        print delay_seconds
        self.fuse_text.SetText('%05.1f' % delay_seconds)

        #self.launch_missile( Objects.PLAYER, angle, delay )

    def manual_firing(self, state):
        print 'manual',state
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

        handled,dragging = super(GameView,self).MouseButtonDown(screen_pos,button)

        if handled:
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
        elif self.zooming:
            self.AdjustZoom(-rel.y/100.0,globals.screen/2)

    def AdjustZoom(self,amount,pos):
        #hack to get the zooming right
        pos -= Point(320,180)
        pos_coords = self.viewpos.Get() + (pos/self.zoom)
        oldzoom = self.zoom

        self.zoom -= (amount/10.0)
        if self.zoom > 4:
            self.zoom = 4

        #if we've zoomed so far out that we can see an edge of the screen, fix that
        top_left= Point(0,globals.screen.y/self.zoom)
        top_right = globals.screen/self.zoom
        bottom_right = Point(globals.screen.x/self.zoom,0)

        new_viewpos = self.viewpos.Get()
        if new_viewpos.y < 0:
            new_viewpos.y = 0

        if new_viewpos.x < 0:
            new_viewpos.x = 0

        #now the top left
        new_top_right = new_viewpos+top_right
        if new_top_right.y  > self.absolute.size.y:
            new_viewpos.y -= (new_top_right.y - self.absolute.size.y)

        if new_top_right.x > self.absolute.size.x:
            new_viewpos.x -= (new_top_right.x - self.absolute.size.x)

        try:
            if new_viewpos.y < 0:
                raise ValueError

            if new_viewpos.x < 0:
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
        self.viewpos.Set(self.viewpos.Get() + (pos_coords - new_pos_coords))

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
        #rejig stuff

        # for t, state in self.future_state:
        #     state[Objects.PLAYER].line_seg.Delete()
        # for t, state in self.future_state:
        #     del state[Objects.PLAYER]

        # d = 50 if key == 45 else -50
        # self.initial_state[Objects.PLAYER].velocity += Point(0,d)
        # self.fill_state_obj(Objects.PLAYER)
        if key not in [pygame.K_UP, pygame.K_LEFT, pygame.K_DOWN, pygame.K_RIGHT]:
            self.mode.KeyDown(key)

    def KeyUp(self,key):
        if key == pygame.K_DELETE:
            if self.music_playing:
                self.music_playing = False
                pygame.mixer.music.set_volume(0)
            else:
                self.music_playing = True
                pygame.mixer.music.set_volume(1)
        if key == pygame.K_SPACE:
            self.start_scan()
        if key == pygame.K_RETURN:
            self.stabalise_orbit(Objects.PLAYER)
        if key == pygame.K_RETURN:
            self.lock_on(self.enemy)
        self.mode.KeyUp(key)

