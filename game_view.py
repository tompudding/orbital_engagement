from OpenGL.GL import *
import random,numpy,cmath,math,pygame

import ui,globals,drawing,os,copy
from globals.types import Point
import modes
import random

class FixedBody(object):
    def __init__(self, pos):
        self.pos = pos.to_float()
        self.quad = drawing.Quad(globals.quad_buffer, tc=globals.atlas.TextureSpriteCoords(self.texture_name))
        self.set_vertices()

    def set_vertices(self):
        bl = self.pos - Point(16,16)
        tr = bl + Point(32,32)
        self.quad.SetVertices(bl, tr, self.height)

    def acc_due_to_gravity(self, body):
        vector = (self.pos - body.pos) * globals.pixels_to_units
        return (vector / vector.SquareLength()) * self.mass

class Sun(FixedBody):
    height = 9000
    texture_name = 'sun.png'
    mass = 100000000

class Ship(FixedBody):
    texture_name = 'ship.png'
    mass = 1
    height = 8000
    def __init__(self, pos, parent):
        super(Ship, self).__init__(pos)
        self.velocity = (Point(1,-1).unit_vector()) * 10000
        self.last = globals.time
        self.parent = parent

    def Update(self):
        elapsed = (globals.time - self.last) * globals.time_factor
        self.last = globals.time
        #Force due to gravity
        acc = Point(0,0)
        for body in self.parent.fixed_bodies:
            acc += body.acc_due_to_gravity(self)

        self.velocity += acc * elapsed

        distance_travelled = self.velocity * elapsed
        self.pos += (distance_travelled * globals.units_to_pixels)
        #print acc,self.velocity,self.pos
        #print (self.pos - self.parent.fixed_bodies[0].pos).length()

        self.set_vertices()


class GameView(ui.RootElement):
    def __init__(self):
        self.atlas = globals.atlas = drawing.texture.TextureAtlas('tiles_atlas_0.png','tiles_atlas.txt')
        self.game_over = False
        #pygame.mixer.music.load('music.ogg')
        #self.music_playing = False
        super(GameView,self).__init__(Point(0,0),globals.screen)
        self.square = drawing.Line(globals.line_buffer)
        self.square.SetVertices( Point(0,0), Point(1000,1000), 1000)
        self.square.SetColour( (1,0,0,1) )
        self.sun = Sun(Point(0,0))
        self.fixed_bodies = [self.sun]
        self.ship = Ship(Point(100,100), self)
        #skip titles for development of the main game
        #self.mode = modes.Titles(self)
        self.viewpos = Point(-640,-360)

        self.mode = modes.Combat(self)
        self.StartMusic()

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

        self.ship.Update()

        if self.game_over:
            return

        self.t = t

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

