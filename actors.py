from globals.types import Point
from OpenGL.GL import *
import globals
import ui
import drawing
import os
import game_view
import random
import pygame
import cmath
import math
import numpy
import modes


class Actor(object):
    texture = None
    width   = None
    height  = None
    threshold = 0.01
    initial_health = 100
    max_speed = 0.25
    max_square_speed = max_speed**2
    def __init__(self,map,pos):
        self.map            = map
        self.tc             = globals.atlas.TextureSpriteCoords('%s.png' % self.texture)
        self.quad           = drawing.Quad(globals.quad_buffer,tc = self.tc)
        self.size           = Point(float(self.width)/16,float(self.height)/16)
        self.corners = self.size, Point(-self.size.x,self.size.y), Point(-self.size.x,-self.size.y), Point(self.size.x,-self.size.y)
        self.corners        = [p*0.5 for p in self.corners]
        self.corners_polar  = [(p.length(),((1+i*2)*math.pi)/4) for i,p in enumerate(self.corners)]
        self.radius_square  = (self.size.x/2)**2 + (self.size.y/2)**2
        self.radius         = math.sqrt(self.radius_square)
        self.corners_euclid = [p for p in self.corners]
        self.current_sound  = None
        self.last_update    = None
        self.dead           = False
        self.move_speed     = Point(0,0)
        self.angle_speed    = 0
        self.move_direction = Point(0,0)
        self.pos = None
        self.last_damage = 0
        self.health = self.initial_health
        self.interacting = None
        self.SetPos(pos)
        self.set_angle(3*math.pi/2)
        self.hand_offset = Point(0,self.size.y*1.1)
        self.track_quads = []
        self.last_track = 0

    def mid_point(self):
        return self.pos + (self.size/2).Rotate(self.angle)

    def RemoveFromMap(self):
        if self.pos is not None:
            bl = self.pos.to_int()
            tr = (self.pos+self.size).to_int()
            for x in xrange(bl.x,tr.x+1):
                for y in xrange(bl.y,tr.y+1):
                    self.map.RemoveActor(Point(x,y),self)

    def AdjustHealth(self,amount):
        self.health += amount
        if self.health > self.initial_health:
            self.health = self.initial_health
        if self.health < 0:
            #if self.dead_sound:
            #    self.dead_sound.play()
            self.health = 0
            self.dead = True
            self.Death()

    def damage(self, amount):
        if globals.time < self.last_damage + self.immune_duration:
            #woop we get to skip
            return
        self.last_damage = globals.time
        self.AdjustHealth(-amount)

    def SetPos(self,pos):
        self.RemoveFromMap()
        self.pos = pos

        self.vertices = [((pos + corner)*globals.tile_dimensions).to_int() for corner in self.corners_euclid]

        bl = pos
        tr = bl + self.size
        bl = bl.to_int()
        tr = tr.to_int()
        #self.quad.SetVertices(bl,tr,4)
        self.quad.SetAllVertices(self.vertices, 4)
        for x in xrange(bl.x,tr.x+1):
            for y in xrange(bl.y,tr.y+1):
                self.map.AddActor(Point(x,y),self)

    def TriggerCollide(self,other):
        pass


    def set_angle(self, angle):
        self.angle = angle%(2*math.pi)
        self.corners_polar  = [(p.length(),self.angle + ((1+i*2)*math.pi)/4) for i,p in enumerate(self.corners)]
        cnums = [cmath.rect(r,a) for (r,a) in self.corners_polar]
        self.corners_euclid = [Point(c.real,c.imag) for c in cnums]

    def Update(self,t):
        self.Move(t)

    def hand_pos(self):
        return self.pos + self.hand_offset.Rotate(self.angle)

    def Move(self,t):
        if self.last_update is None:
            self.last_update = globals.time
            return
        elapsed = (globals.time - self.last_update)*globals.time_step
        self.last_update = globals.time

        angle_change = self.angle_speed*elapsed
        if 0 != self.required_turn:
            self.turned += abs(angle_change)
        self.set_angle(self.angle + angle_change)

        self.move_speed += self.move_direction.Rotate(self.angle)*elapsed
        if self.move_speed.SquareLength() > self.max_square_speed:
            self.move_speed = self.move_speed.unit_vector() * self.max_speed

        mp = self.mid_point().to_int()
        try:
            tile = self.map.data[mp.x][mp.y]
            if tile.type == game_view.TileTypes.ICE:
                friction = 0.002*elapsed
                if not globals.wee_played:
                    globals.sounds.weee.play()
                    globals.wee_played = True
            else:
                friction = 0.05*elapsed

        except IndexError:
            friction = 0.05*elapsed

        if friction:
            friction = self.move_speed.unit_vector()*friction
            if friction.SquareLength() < self.move_speed.SquareLength():
            #self.move_speed *= 0.7*(1-(elapsed/1000.0))
                self.move_speed -= friction
            else:
                self.move_speed = Point(0,0)

        if tile.type != game_view.TileTypes.ICE:#There's friction so also make some tracks
            if globals.time - self.last_track > 10 and self.move_speed.SquareLength() > 0.001 or abs(angle_change) > 0.001:
                self.last_track = globals.time
                quad = drawing.Quad(globals.quad_buffer,tc = globals.atlas.TextureSpriteCoords('tracks.png'))
                quad.SetAllVertices(self.vertices, 0.5)
                self.track_quads.append(quad)
                if len(self.track_quads) > 10000:
                    q = self.track_quads.pop(0)
                    q.Delete()

        if self.interacting:
            self.move_speed = Point(0,0)

        amount = self.move_speed * elapsed 

        bl = self.pos.to_int()
        tr = (self.pos+self.size).to_int()
        for x in xrange(bl.x,tr.x+1):
            for y in xrange(bl.y,tr.y+1):
                try:
                    for actor in self.map.data[x][y].actors:
                        if actor is self:
                            continue
                        distance = actor.pos - self.pos
                        if distance.SquareLength() < self.radius_square + actor.radius_square:
                            overlap = self.radius + actor.radius - distance.length()
                            adjust = distance.unit_vector()*-overlap
                            amount += adjust*0.1
                            self.TriggerCollide(actor)
                            #We've hit, so move us away from it's centre by the overlap
                except IndexError:
                    pass

        #check each of our four corners
        for corner in self.corners:
            pos = self.pos + corner
            target_x = pos.x + amount.x
            if target_x >= self.map.size.x:
                amount.x = 0
                target_x = pos.x
            elif target_x < 0:
                amount.x = -pos.x
                target_x = 0

            target_tile_x = self.map.data[int(target_x)][int(pos.y)]
            if target_tile_x.type in game_view.TileTypes.Impassable:
                amount.x = 0

            elif (int(target_x),int(pos.y)) in self.map.object_cache:
                obj = self.map.object_cache[int(target_x),int(pos.y)]
                if obj.Contains(Point(target_x,pos.y)):
                    amount.x = 0

            target_y = pos.y + amount.y
            if target_y >= self.map.size.y:
                amount.y = 0
                target_y = pos.y
            elif target_y < 0:
                amount.y = -pos.y
                target_y = 0
            target_tile_y = self.map.data[int(pos.x)][int(target_y)]
            if target_tile_y.type in game_view.TileTypes.Impassable:
                amount.y = 0
            elif (int(pos.x),int(target_y)) in self.map.object_cache:
                obj = self.map.object_cache[int(pos.x),int(target_y)]
                if obj.Contains(Point(pos.x,target_y)):
                    amount.y = 0


        self.SetPos(self.pos + amount)

        if self.interacting:
            diff = self.interacting.pos + (self.interacting.size*0.5) - self.pos
            distance = diff.length()
            if distance > 2.5:
                self.deactivate()

    def GetPos(self):
        return self.pos

    def GetPosCentre(self):
        return self.pos

    def click(self, pos, button):
        pass

    def unclick(self, pos, button):
        pass

    @property
    def screen_pos(self):
        p = (self.pos*globals.tile_dimensions - globals.game_view.viewpos._pos)*globals.scale
        return p


class Light(object):
    z = 60
    def __init__(self,pos,radius = 400, intensity = 1):
        self.radius = radius
        self.width = self.height = radius
        self.quad_buffer = drawing.QuadBuffer(4)
        self.quad = drawing.Quad(self.quad_buffer)
        self.shadow_quad = globals.shadow_quadbuffer.NewLight()
        self.shadow_index = self.shadow_quad.shadow_index
        self.colour = (1,1,1)
        self.intensity = float(intensity)
        self.set_pos(pos)
        self.on = True
        self.append_to_list()

    def append_to_list(self):
        globals.lights.append(self)

    def set_pos(self,pos):
        self.world_pos = pos
        pos = pos*globals.tile_dimensions
        self.pos = (pos.x,pos.y,self.z)
        box = (globals.tile_scale*Point(self.width,self.height))
        bl = Point(*self.pos[:2]) - box*0.5
        tr = bl + box
        bl = bl.to_int()
        tr = tr.to_int()
        self.quad.SetVertices(bl,tr,4)

    def Update(self,t):
        pass

    @property
    def screen_pos(self):
        p = self.pos
        return ((p[0] - globals.game_view.viewpos._pos.x)*globals.scale.x,(p[1]-globals.game_view.viewpos._pos.y)*globals.scale.y,self.z)

class NonShadowLight(Light):
    def append_to_list(self):
        globals.non_shadow_lights.append(self)

class ActorLight(object):
    z = 6
    def __init__(self,parent):
        self.parent = parent
        self.quad_buffer = drawing.QuadBuffer(4)
        self.quad = drawing.Quad(self.quad_buffer)
        self.colour = (1,1,1)
        self.radius = 30
        self.intensity = 1
        self.on = True
        globals.non_shadow_lights.append(self)

    def Update(self,t):
        self.vertices = [((self.parent.pos + corner*2)*globals.tile_dimensions).to_int() for corner in self.parent.corners_euclid]
        self.quad.SetAllVertices(self.vertices, 0)

    @property
    def pos(self):
        return (self.parent.pos.x*globals.tile_dimensions.x,self.parent.pos.y*globals.tile_dimensions.y,self.z)

class MorseLight(object):
    z = 6
    def __init__(self,parent,colour):
        self.parent = parent
        self.quad_buffer = drawing.QuadBuffer(4)
        self.quad = drawing.Quad(self.quad_buffer)
        self.colour = colour
        self.radius = 60
        self.intensity = 1
        self.on = True
        globals.non_shadow_lights.append(self)

    def Update(self,t):
        self.vertices = [((self.parent.pos + corner*3)*globals.tile_dimensions).to_int() for corner in self.parent.corners_euclid]
        self.quad.SetAllVertices(self.vertices, 0)

    @property
    def pos(self):
        return (self.parent.pos.x*globals.tile_dimensions.x,self.parent.pos.y*globals.tile_dimensions.y,self.z)


class FixedLight(object):
    z = 6
    def __init__(self,pos,size):
        #self.world_pos = pos
        self.pos = pos*globals.tile_dimensions
        self.size = size
        self.quad_buffer = drawing.QuadBuffer(4)
        self.quad = drawing.Quad(self.quad_buffer)
        self.colour = (0.2,0.2,0.2)
        self.on = True
        globals.uniform_lights.append(self)
        self.pos = (self.pos.x,self.pos.y,self.z)
        box = (self.size*globals.tile_dimensions)
        bl = Point(*self.pos[:2])
        tr = bl + box
        bl = bl.to_int()
        tr = tr.to_int()
        self.quad.SetVertices(bl,tr,4)


class ConeLight(object):
    width = 700
    height = 700
    z = 60
    def __init__(self,pos,angle,width):
        self.quad_buffer = drawing.QuadBuffer(4)
        self.quad = drawing.Quad(self.quad_buffer)
        self.shadow_quad = globals.shadow_quadbuffer.NewLight()
        self.shadow_index = self.shadow_quad.shadow_index
        self.colour = (1,1,1)
        self.initial_angle = angle
        self.angle = angle
        self.angle_width = width
        self.on = True
        pos = pos*globals.tile_dimensions
        self.world_pos = pos
        self.pos = (pos.x,pos.y,self.z)
        box = (globals.tile_scale*Point(self.width,self.height))
        bl = Point(*self.pos[:2]) - box*0.5
        tr = bl + box
        bl = bl.to_int()
        tr = tr.to_int()
        self.quad.SetVertices(bl,tr,4)
        globals.cone_lights.append(self)

    @property
    def screen_pos(self):
        p = self.pos
        out =  ((p[0] - globals.game_view.viewpos._pos.x)*globals.scale.x,(p[1]-globals.game_view.viewpos._pos.y)*globals.scale.y,self.z)
        return out

class Torch(ConeLight):
    def __init__(self,parent,offset):
        self.quad_buffer = drawing.QuadBuffer(4)
        self.quad = drawing.Quad(self.quad_buffer)
        self.shadow_quad = globals.shadow_quadbuffer.NewLight()
        self.shadow_index = self.shadow_quad.shadow_index
        self.parent = parent
        self.last_update    = None
        self.colour = (1,1,1)
        self.angle = 0.0
        self.offset = cmath.polar(offset.x + offset.y*1j)
        self.angle_width = 0.7
        self.on = True
        globals.cone_lights.append(self)

    @property
    def world_pos(self):
        offset = cmath.rect(self.offset[0],self.offset[1]+self.parent.angle)
        pos = (self.parent.pos + Point(offset.real,offset.imag))
        return (pos.x,pos.y,self.z)

    @property
    def pos(self):
        offset = cmath.rect(self.offset[0],self.offset[1]+self.parent.angle)
        pos = (self.parent.pos + Point(offset.real,offset.imag))*globals.tile_dimensions
        return (pos.x,pos.y,self.z)

    def Update(self,t):
        self.angle = (self.parent.angle + math.pi*0.5)%(2*math.pi)
        box = (globals.tile_scale*Point(self.width,self.height))
        bl = Point(*self.pos[:2]) - box*0.5
        tr = bl + box
        bl = bl.to_int()
        tr = tr.to_int()
        self.quad.SetVertices(bl,tr,4)
        #self.quad.SetAllVertices(self.parent.vertices, 0)


class Robot(Actor):
    texture = 'robot'
    width = 24
    height = 24
    forward_speed = Point( 0.00, 0.1)
    rotation_speed = 0.04
    name = 'unknown'

    def __init__(self,map,pos):
        super(Robot,self).__init__(map,pos)
        self.light = ActorLight(self)
        self.morse_light = MorseLight(self,self.morse_colour)
        self.morse_light.on = False
        self.info_window = self.map.parent.robot_window
        self.commands = {'f' : self.forward,
                         'b' : self.back,
                         'l' : self.left,
                         'r' : self.right}
        self.command_info = [('F<num>' , 'forward <num> units'),
                             ('B<num>' , 'back <num> units'),
                             ('L<num>' , 'turn left <num>'),
                             ('R<num>' , 'turn right <num>')]
        self.setup_info()
        self.move_end = None
        self.target_angle = self.angle
        self.turned = 0
        self.required_turn = 0
        offset = Point(-(self.width/globals.tile_dimensions.x)*0.6,0)
        self.torch = Torch(self,offset.Rotate(self.angle))

    def setup_info(self):
        #Title in the middle at the top
        self.info = ui.UIElement(parent=self.info_window,
                                 pos = Point(0,0),
                                 tr = Point(1,1))
        self.info.name = ui.TextBox(parent=self.info,
                                    bl=Point(0,0.8),
                                    tr=Point(1,1),
                                    text=self.name,
                                    scale=8,
                                    colour=self.map.parent.text_colour,
                                    alignment=drawing.texture.TextAlignments.CENTRE)
        num_rows = 10
        num_cols = 1
        margin_height_top = 0.1
        margin_height_bottom = 0.02
        margin_width  = -0.045
        height = (1.0-(margin_height_top+margin_height_bottom))/num_rows
        width  = (1.0-2*margin_width)/num_cols
        self.info.commands = []
        for i,(command,info) in enumerate(self.command_info):
            x = margin_width + (i/num_rows)*width
            y = margin_height_bottom + (num_rows - 1 - (i%num_rows))*height
            item = ui.TextBox(parent = self.info,
                              bl = Point(x,y),
                              tr = Point(x+width,y+height),
                              scale=6,
                              text = '%s: %s' % (command,info),
                              colour=self.map.parent.text_colour)
            self.info.commands.append(item)
        self.info.Disable()


    def Update(self,t):
        self.torch.Update(t)
        if self.move_end and t >= self.move_end:
            self.move_direction = Point(0,0)
            self.move_end = None
            globals.sounds.move.fadeout(100)
        if self.turned > self.required_turn:
            self.done_turn()

        super(Robot,self).Update(t)
        self.light.Update(t)
        self.morse_light.Update(t)

    def done_turn(self):
        self.angle_speed = 0
        self.turned = 0
        self.required_turn = 0
        self.angle = self.target_angle
        self.target_angle = 0

    def Select(self):
        self.info.Enable()

    def UnSelect(self):
        self.info.Disable()

    def move_command(self,command,multiplier):
        try:
            distance = int(command)
        except ValueError:
            globals.game_view.recv_morse.play('IN '+command, self.morse_light)
            return
        self.move_direction = self.forward_speed*multiplier
        self.move_end = globals.time + (distance*420/abs(multiplier))
        globals.sounds.move.play()
        globals.game_view.recv_morse.play('OK', self.morse_light)

    def forward(self,command):
        self.move_command(command,1)

    def back(self,command):
        self.move_command(command,-0.6)

    def turn_command(self,command,multiplier):
        try:
            command = abs(int(command))
        except ValueError:
            return
        if command == 0:
            return
        try:
            angle = float(command)*math.pi/180
        except ValueError:
            globals.game_view.recv_morse.play('IN '+command, self.morse_light)
            return
        self.begin_turn(angle,multiplier)
        globals.game_view.recv_morse.play('OK', self.morse_light)

    def begin_turn(self,angle,multiplier):
        self.angle_speed = self.rotation_speed*multiplier
        self.target_angle = (self.angle + angle*multiplier)%(2*math.pi)
        self.required_turn = angle
        self.turned = 0
        globals.sounds.move.play()


    def left(self,command):
        self.turn_command(command,1)

    def right(self,command):
        self.turn_command(command,-1)

    def execute_command(self,command):
        command = command.lower()
        command_name,command_data = command[:1],command[1:]
        try:
            self.commands[command_name](command_data)
        except KeyError:
            globals.game_view.recv_morse.play('UC '+command_name, self.morse_light)


class ActivatingRobot(Robot):
    name = 'Activator'
    morse_colour = (1,1,0)

    def __init__(self,map,pos):
        super(ActivatingRobot,self).__init__(map,pos)
        self.mark_quads = []
        self.num_marked = 0

    def setup_info(self):
        #Add special commands
        self.scanning = False
        self.commands['a'] = self.activate
        self.commands['s'] = self.scan
        self.commands['m'] = self.mark
        self.command_info.append( ('A','Activate') )
        self.command_info.append( ('S','Scan') )
        self.command_info.append( ('M','Mark') )
        super(ActivatingRobot,self).setup_info()

    def activate(self,command=None):
        #There's a precise and quick way of doing this, but due to not knowing exactly where in a tile we are,
        #and issues about which tile we're pointing into (it might be the same one), we'll take a shitty approach
        #and just loop over all the objects to see if they're close enough to us
        for door in self.map.doors:
            distance = (self.hand_pos() - door.mid_point).length()
            if distance < 1:
                door.Interact(self)
                break

    def scan(self,command):
        #The scan will find three things:
        # - The other robot
        # - The axe
        # - The candy cane
        messages = ['SR']
        self.move_end = globals.time-1
        globals.sounds.move.fadeout(100)
        other_robot = self.map.robots[0]
        items = [('AX',self.map.axe_position+Point(0.5,0.5)),
                 ('CC',self.map.candy.mid_point),
                 ('RB',other_robot.mid_point())]
        if other_robot.axe:
            items = items[1:]
        globals.sounds.scanning.play()

        for name,item in items:
            vector = (self.mid_point() - item).Rotate((math.pi*0.5)-self.angle)
            distance = vector.length()
            r,a = cmath.polar(vector.x + vector.y*1j)
            a = (a + math.pi*2)%(math.pi*2)
            bearing = a*180.0/math.pi
            #we want it to be clockwise
            bearing = 360 - bearing
            distance = r/1.95
            message = '%s DS %d BR %d' % (name,int(distance),int(bearing))
            messages.append(message)
        globals.game_view.recv_morse.play('\n'.join(messages), self.morse_light)

        self.torch.colour = (0,0,1)
        self.begin_turn(math.pi*2,1)
        self.scanning = True

    def mark(self,command):
        #Stick a mark quad exactly where we are
        quad = drawing.Quad(globals.quad_buffer,tc = globals.atlas.TextureSpriteCoords('mark.png'))
        quad.SetAllVertices(self.vertices, 1 + self.num_marked*0.01)
        self.num_marked += 1
        self.mark_quads.append(quad)
        globals.sounds.mark.play()
        if len(self.mark_quads) > 100:
            q = self.mark_quads.pop(0)
            q.Delete()

    def done_turn(self):
        super(ActivatingRobot,self).done_turn()
        globals.sounds.move.fadeout(100)
        if self.scanning:
            self.torch.colour = (1,1,1)
            self.scanning = False


class BashingRobot(Robot):
    texture = 'robot_blue'
    name = 'Chopper'
    chop_duration = 300
    morse_colour = (1,1,0)

    def __init__(self,map,pos):
        self.axe = False
        self.chop_end = None
        super(BashingRobot,self).__init__(map,pos)
        self.axe_quad = drawing.Quad(globals.quad_buffer,tc = globals.atlas.TextureSpriteCoords('axe.png'))
        self.axe_offset = Point(self.size.x*0.6,self.size.y*0.2)
        self.axe = False
        self.axe_quad.Disable()
        self.axe_angle = 0
        self.dig_quads = []
        self.num_dug = 0
        #Temp hack for debugging
        #self.found_axe()


    def SetPos(self,pos):
        super(BashingRobot,self).SetPos(pos)
        if self.axe:
            offset = self.axe_offset.Rotate(self.angle)
            vertices = [(offset + corner).Rotate(self.axe_angle)*globals.tile_dimensions for corner in self.corners_euclid]
            vertices = [(pos*globals.tile_dimensions + c).to_int() for c in vertices]
            self.axe_quad.SetAllVertices(vertices, 4.1)

    def setup_info(self):
        #Add special commands
        self.commands['d'] = self.dig
        self.commands['c'] = self.chop
        self.command_info.append( ('D','Dig for item') )
        self.command_info.append( ('C','Chop with axe') )
        super(BashingRobot,self).setup_info()

    def dig(self,command):
        #Stick a mark quad exactly where we are
        quad = drawing.Quad(globals.quad_buffer,tc = globals.atlas.TextureSpriteCoords('dig.png'))
        quad.SetAllVertices(self.vertices, 1.1 + self.num_dug*0.01)
        self.num_dug += 1
        self.dig_quads.append(quad)
        if len(self.dig_quads) > 100:
            q = self.dig_quads.pop(0)
            q.Delete()


        axe = self.map.axe_position+Point(0.5,0.5)
        distance = (self.mid_point() - axe).length()
        if distance < 5:
            #We found the axe!
            self.found_axe()
        else:
            globals.sounds.dig.play()

    def found_axe(self):
        self.axe = True
        self.axe_quad.Enable()
        globals.sounds.axe.play()
        self.map.parent.recv_morse.play('AX FND', self.morse_light)

    def Update(self,t):
        if self.chop_end:
            if t > self.chop_end:
                self.finish_chop()
            else:
                partial = 1 - float(self.chop_end - t)/self.chop_duration
                if partial < 0.5:
                    self.axe_angle = partial*2*math.pi*0.5
                else:
                    partial = 1-partial
                    self.axe_angle = partial*2*math.pi*0.5
        super(BashingRobot,self).Update(t)

    def chop(self,command):
        if not self.axe:
            globals.game_view.recv_morse.play('NO AX', self.morse_light)
            return
        self.chop_end = globals.time + self.chop_duration
        #play chop sound
        globals.sounds.chop.play()
        target = self.mid_point() + (Point(0,1).Rotate(self.angle))

        try:
            target_tile = self.map.data[int(target.x)][int(target.y)]
        except IndexError:
            self.chop_target = None
            return

        self.chop_target = target_tile

    def finish_chop(self):
        if self.chop_target and self.chop_target.type in game_view.TileTypes.Choppable:
            self.chop_target.chop_down()
        self.chop_target = None
        self.axe_angle = 0
