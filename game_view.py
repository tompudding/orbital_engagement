from OpenGL.GL import *
import random,numpy,cmath,math,pygame

import ui,globals,drawing,os,copy
from globals.types import Point
import modes
import random
import cmath

G = 1

class Body(object):
    def __init__(self, pos, velocity, mass, last_pos = None):
        self.pos = pos
        self.velocity = velocity
        self.mass = mass
        if last_pos:
            self.line_seg = drawing.Line(globals.line_buffer)
            self.line_seg.SetVertices( last_pos , self.pos, 1000 )

    def step(self, elapsed, gravity_sources, line=True):
        acc = Point(0,0)
        for body in gravity_sources:
            acc += body.acc_due_to_gravity(self)

        velocity = self.velocity + (acc * elapsed)
        distance_travelled = self.velocity * elapsed

        pos = self.pos + (distance_travelled * globals.units_to_pixels)

        return Body(pos, velocity, self.mass, self.pos if line else None)

    def acc_due_to_gravity(self, body):
        vector = (self.pos - body.pos) * globals.pixels_to_units
        return (vector / vector.SquareLength()) * self.mass * G

    def apply_force_towards(self, target, force):
        vector = ((target.pos - self.pos).unit_vector())
        acc = ((vector * force)/ self.mass)
        self.velocity += acc


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
    mass = 1
    height = 8000

class Objects:
    SUN  = 0
    PLAYER = 1
    ENEMY  = 2
    mobile = [PLAYER, ENEMY]

line_colours = { Objects.PLAYER : (0,0,1),
                 Objects.ENEMY  : (1,0,0) }

class GameView(ui.RootElement):
    step_time = 1000
    def __init__(self):
        self.atlas = globals.atlas = drawing.texture.TextureAtlas('tiles_atlas_0.png','tiles_atlas.txt')
        self.game_over = False
        #pygame.mixer.music.load('music.ogg')
        #self.music_playing = False
        super(GameView,self).__init__(Point(0,0),globals.screen)
        #self.square = drawing.Line(globals.line_buffer)
        #self.square.SetVertices( Point(0,0), Point(1000,1000), 1000)
        #self.square.SetColour( (1,0,0,1) )
        self.sun = Sun()
        self.ship = Ship()
        self.enemy = Ship()
        self.sun_body  = FixedBody( pos=Point(0,0), velocity=Point(0,0), mass=100000000 )
        self.sun.set_vertices(self.sun_body.pos)
        orbit_velocity = (math.sqrt(G * self.sun_body.mass / (100)))
        print orbit_velocity
        orbit_velocity = orbit_velocity*280
        orbit_velocity = 10000
        self.ship_body = Body( Point(100, 0), (Point(0,-1).unit_vector()) * orbit_velocity, mass=1 )
        self.enemy_body = Body( Point(-100, -100), (Point(-1,1).unit_vector()) * 12000, mass=1 )
        self.fixed_bodies = [self.sun_body]
        self.initial_state = { Objects.PLAYER : self.ship_body,
                               Objects.ENEMY  : self.enemy_body,
                               Objects.SUN    : self.sun_body }
        self.object_quads = { Objects.PLAYER : self.ship,
                              Objects.ENEMY : self.enemy }
        #set up the state
        self.future_state = []
        self.fill_state()
        #skip titles for development of the main game
        #self.mode = modes.Titles(self)
        self.viewpos = Point(-640,-360)
        self.temp_bodies = []
        self.last = None

        self.mode = modes.Combat(self)
        self.saved_segs = { Objects.PLAYER : [],
                            Objects.ENEMY : [] }
        self.StartMusic()

    def fill_state(self):
        try:
            current,state = self.future_state[-1]
        except IndexError:
            current = globals.time
            state = self.initial_state
        t = current + self.step_time
        period = 8000.0

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
            #self.future_state[0][1][obj_type].line_seg.SetColour( (0,0,0,0) )
            for i in xrange(0, len(self.future_state)):
                intensity = 1 - ((self.future_state[i][0] - self.future_state[0][0])/period)
                try:
                    col = line_colours[obj_type] + (intensity, )
                    self.future_state[i][1][obj_type].line_seg.SetColour( col )
                except KeyError:
                    continue

    def fill_state_obj(self, obj_type):
        last = self.initial_state[obj_type]
        for t, state in self.future_state:
            if obj_type not in state:
                n = last.step(self.step_time * globals.time_factor, self.fixed_bodies)
                state[obj_type] = n
            last = state[obj_type]

    def StartMusic(self):
        pass
        #pygame.mixer.music.play(-1)
        #self.music_playing = True

    def Draw(self):
        drawing.ResetState()
        #drawing.Translate(-400,-400,0)
        s = 1.0
        drawing.Scale(s,s,1)
        drawing.Translate(-self.viewpos.x/s,-self.viewpos.y/s,0)


        drawing.DrawNoTexture(globals.line_buffer)
        drawing.DrawNoTexture(globals.colour_tiles)
        drawing.DrawAll(globals.quad_buffer,self.atlas.texture)

        #drawing.DrawAll(globals.nonstatic_text_buffer,globals.text_manager.atlas.texture)

    def scan_for_player(self):
        #Throw out a bunch of rays and see if any of them collide with the player's current ray
        diff = self.initial_state[Objects.PLAYER].pos - self.initial_state[Objects.ENEMY].pos
        distance, angle_to_player = cmath.polar(diff[0] + diff[1]*1j)
        gap = math.pi/32
        angle_guesses = [angle_to_player + i*gap for i in xrange(-16,16)]
        #for b in self.temp_bodies:
        #    b.line_seg.Delete()
        self.temp_bodies = []
        period = 40000.0
        best_time = period
        explosion_distance = 100
        for angle in angle_guesses:
            body = self.initial_state[Objects.ENEMY]
            v = cmath.rect(20000, angle)
            velocity = Point(v.real, v.imag)
            body = Body(body.pos, body.velocity + velocity, body.mass)
            step = 1000
            t = globals.time


            while t < globals.time + period:
                target = self.get_obj_at_time(Objects.PLAYER, t)
                if target:
                    distance = (target.pos - body.pos).length()
                    if distance < explosion_distance and (t - globals.time) < best_time:
                        best_time = t - globals.time
                        print angle,best_time,distance
                    #body.apply_force_towards( target, 1000 )
                body = body.step(step * globals.time_factor, self.fixed_bodies, line = False)
                self.temp_bodies.append(body)
                t += step
        #for body in self.temp_bodies:
        #    body.line_seg.SetColour( (1,1,1,1) )

    def get_obj_at_time(self, obj_type, target):
        #Get the first one before it
        closest_before = None
        closest_after = None
        for i, (t, state) in enumerate(self.future_state):
            if t < target:
                closest_before = state[obj_type]
            if t > globals.time:
                closest_after = state[obj_type]
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

        if self.last is None:
            self.last = globals.time
        else:
            elapsed = globals.time - self.last
            self.last = globals.time
            for obj_type in Objects.mobile:
                n = self.initial_state[obj_type].step(elapsed * globals.time_factor, self.fixed_bodies, line = False)
                self.object_quads[obj_type].set_vertices( n.pos )
                self.initial_state[obj_type] = n


        if self.future_state[0][0] < globals.time:
            #Kill the line segments that are in the future
            for t,state in self.future_state:
                for obj_type in Objects.mobile:
                    if t > globals.time:
                        state[obj_type].line_seg.Delete()
                    else:
                        #For the others store them for later deletion
                        self.saved_segs[obj_type].append( (t, state[obj_type].line_seg ) )

            self.future_state = []
            self.fill_state()
            #Now there's been an update, let's see if we can get a firing solution on the player :)
            self.scan_for_player()

        for obj_type in Objects.mobile:
            new_saved = []
            for (t,line_seg) in self.saved_segs[obj_type]:
                age = globals.time - t
                if age < 10000:
                    new_saved.append( (t,line_seg) )
                elif age > 10000 + 8000:
                    line_seg.Delete()
                else:
                    intensity = 1 - ((age - 10000) / 8000.0)
                    col = line_colours[obj_type] + (intensity, )
                    line_seg.SetColour( col )
                    new_saved.append( (t,line_seg) )
            self.saved_segs[obj_type] = new_saved

        if self.game_over:
            return

    def GameOver(self):
        self.game_over = True
        self.mode = modes.GameOver(self)

    def KeyDown(self,key):
        #rejig stuff

        for t, state in self.future_state:
            state[Objects.PLAYER].line_seg.Delete()
        for t, state in self.future_state:
            del state[Objects.PLAYER]

        d = 50 if key == 45 else -50
        self.initial_state[Objects.PLAYER].velocity += Point(0,d)
        self.fill_state_obj(Objects.PLAYER)
        self.mode.KeyDown(key)

    def KeyUp(self,key):
        if key == pygame.K_DELETE:
            if self.music_playing:
                self.music_playing = False
                pygame.mixer.music.set_volume(0)
            else:
                self.music_playing = True
                pygame.mixer.music.set_volume(1)
        self.mode.KeyUp(key)

