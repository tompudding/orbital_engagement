from OpenGL.GL import *
import random,numpy,cmath,math,pygame

import ui,globals,drawing,os,copy
from globals.types import Point
import modes
import random

class Body(object):
    def __init__(self, pos, velocity, mass):
        self.pos = pos
        self.velocity = velocity
        self.mass = mass

    def step(self, elapsed, gravity_sources):
        acc = Point(0,0)
        for body in gravity_sources:
            acc += body.acc_due_to_gravity(self)

        velocity = self.velocity + (acc * elapsed)
        distance_travelled = self.velocity * elapsed

        pos = self.pos + (distance_travelled * globals.units_to_pixels)

        return Body(pos, velocity, self.mass)

    def acc_due_to_gravity(self, body):
        vector = (self.pos - body.pos) * globals.pixels_to_units
        return (vector / vector.SquareLength()) * self.mass


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
    SHIP = 1

class GameView(ui.RootElement):
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
        self.sun_body  = FixedBody( pos=Point(0,0), velocity=Point(0,0), mass=100000000 )
        self.sun.set_vertices(self.sun_body.pos)
        self.ship_body = Body( Point(100, 100), (Point(1,-1).unit_vector()) * 10000, mass=1 )
        self.fixed_bodies = [self.sun_body]

        #set up the state
        self.future_state = []
        self.fill_state()
        #skip titles for development of the main game
        #self.mode = modes.Titles(self)
        self.viewpos = Point(-640,-360)

        self.mode = modes.Combat(self)
        self.StartMusic()

    def fill_state(self):
        step = 10
        try:
            current,state,line_seg = self.future_state[-1]
            ship = state[Objects.SHIP]
        except IndexError:
            current = globals.time
            ship = self.ship_body
        t = current + step
        last_pos = ship.pos
        while t < globals.time + 8000:
            ship = ship.step(step * globals.time_factor, self.fixed_bodies)
            state = { Objects.SHIP : ship,
                      Objects.SUN  : self.sun_body }
            line_seg = drawing.Line(globals.line_buffer)
            line_seg.SetVertices( last_pos, ship.pos, 1000 )


            last_pos = ship.pos
            self.future_state.append( (t, state, line_seg) )
            t += step

        self.future_state[0][2].SetColour( (1,0,0,1) )
        for i in xrange(1, len(self.future_state)):
            intensity = 1 - ((self.future_state[i][0] - self.future_state[0][0])/8000.0)
            self.future_state[i][2].SetColour( (1,0,0,intensity) )


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

    def Update(self,t):
        if self.mode:
            self.mode.Update(t)

        for i, (t, state, line_seg) in enumerate(self.future_state):
            if t > globals.time:
                break
            line_seg.Delete()

        current_state = self.future_state[i - 1 if i > 0 else 0][1]
        self.ship.set_vertices( current_state[Objects.SHIP].pos )
        self.future_state = self.future_state[i:]

        self.fill_state()

        if self.game_over:
            return



    def GameOver(self):
        self.game_over = True
        self.mode = modes.GameOver(self)

    def KeyDown(self,key):
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

