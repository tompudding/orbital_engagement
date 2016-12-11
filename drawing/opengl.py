import drawing
import os

from OpenGL.arrays import numpymodule
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GL import shaders
from OpenGL.GL.framebufferobjects import *
from globals.types import Point
import globals
import time
import constants
import itertools

numpymodule.NumpyHandler.ERROR_ON_COPY = True

class ShaderLocations(object):
    def __init__(self):
        self.tex               = None
        self.vertex_data       = None
        self.tc_data           = None
        self.colour_data       = None
        self.using_textures    = None
        self.screen_dimensions = None
        self.translation       = None
        self.scale             = None

class ShaderData(object):
    def __init__(self):
        self.program   = None
        self.locations = ShaderLocations()
        self.dimensions = (0, 0, 0)

    def Use(self):
        shaders.glUseProgram(self.program)
        glUniform2f(self.locations.translation, 0, 0)
        glUniform2f(self.locations.scale, 1, 1)
        #state.SetShader(self)
        #state.Update()

    def Load(self,name,uniforms,attributes):
        vertex_name,fragment_name = (os.path.join('drawing','shaders','%s_%s.glsl' % (name,typeof)) for typeof in ('vertex','fragment'))
        codes = []
        for name in vertex_name,fragment_name:
            with open(name,'rb') as f:
                data = f.read()
            codes.append(data)
        VERTEX_SHADER   = shaders.compileShader(codes[0]  , GL_VERTEX_SHADER)
        FRAGMENT_SHADER = shaders.compileShader(codes[1]  , GL_FRAGMENT_SHADER)
        self.program = glCreateProgram()
        shads = (VERTEX_SHADER, FRAGMENT_SHADER)
        for shader in shads:
            glAttachShader(self.program, shader)
        self.fragment_shader_attrib_binding()
        self.program = shaders.ShaderProgram( self.program )
        glLinkProgram(self.program)
        self.program.check_validate()
        self.program.check_linked()
        for shader in shads:
            glDeleteShader(shader)
        #self.program    = shaders.compileProgram(VERTEX_SHADER,FRAGMENT_SHADER)
        for (namelist,func) in ((uniforms,glGetUniformLocation),(attributes,glGetAttribLocation)):
            for name in namelist:
                setattr(self.locations,name,func(self.program,name))

    def fragment_shader_attrib_binding(self):
        pass

class State(object):
    """Stores the state of the tactical viewer; position and scale"""
    def __init__(self,shader):
        self.SetShader(shader)
        self.Reset()

    def SetShader(self,shader):
        self.shader = shader

    def Reset(self):
        self.pos = Point(0,0)
        self.scale = Point(1,1)
        self.Update()

    def Update(self,pos = None, scale = None):
        if pos == None:
            pos = self.pos
        if scale == None:
            scale = self.scale
        if self.shader.locations.translation != None:
            glUniform2f(self.shader.locations.translation, pos.x, pos.y)
        if self.shader.locations.scale != None:
            glUniform2f(self.shader.locations.scale, scale.x, scale.y)


class CrtBuffer(object):
    TEXTURE_TYPE_SHADOW = 0
    NUM_TEXTURES        = 1
    #WIDTH               = 1024
    #HEIGHT              = 256

    def __init__(self, width, height):
        self.fbo = glGenFramebuffers(1)
        self.BindForWriting()
        try:
            self.InitBound(width,height)
        finally:
            self.Unbind()

    def InitBound(self,width,height):
        self.textures      = glGenTextures(self.NUM_TEXTURES)
        if self.NUM_TEXTURES == 1:
            #Stupid inconsistent interface
            self.textures = [self.textures]
        #self.depth_texture = glGenTextures(1)
        glActiveTexture(GL_TEXTURE0)

        for i in xrange(self.NUM_TEXTURES):
            glBindTexture(GL_TEXTURE_2D, self.textures[i])
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA32F, width, height, 0, GL_RGBA, GL_FLOAT, None)
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_BORDER);
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_BORDER);
            glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER, GL_COLOR_ATTACHMENT0 + i, GL_TEXTURE_2D, self.textures[i], 0)

        #glBindTexture(GL_TEXTURE_2D, self.depth_texture)
        #glTexImage2D(GL_TEXTURE_2D, 0, GL_DEPTH_COMPONENT32, width, height, 0, GL_DEPTH_COMPONENT, GL_FLOAT, None)
        #glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_TEXTURE_2D, self.depth_texture, 0)
        glDrawBuffers([GL_COLOR_ATTACHMENT0])

        if glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE:
            print 'crapso1'
            raise SystemExit

    def BindForWriting(self):
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, self.fbo)

    def BindForReading(self,offset):
        self.Unbind()
        for i,texture in enumerate(self.textures):
            glActiveTexture(GL_TEXTURE0 + i + offset)
            glBindTexture(GL_TEXTURE_2D, texture)

    def Unbind(self):
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, 0)


class UIBuffers(object):
    """Simple storage for ui_buffers that need to be drawn at the end of the frame after the scene has been fully rendered"""
    def __init__(self):
        self.Reset()

    def Add(self,quad_buffer,texture):
        if quad_buffer.mouse_relative:
            local_state = (state.pos,state.scale)
        else:
            local_state = None
        if texture != None:
            self.buffers.append( ((quad_buffer,texture,default_shader),local_state,DrawAllNow) )
        else:
            self.buffers.append( ((quad_buffer,default_shader),local_state,DrawNoTextureNow) )

    def Reset(self):
        self.buffers = []

    def Draw(self):
        for args,local_state,func in self.buffers:
            if local_state:
                state.Update(*local_state)

            func(*args)
            if local_state:
                state.Update()

z_max            = 10000
light_shader     = ShaderData()

default_shader   = ShaderData()
crt_shader       = ShaderData()
crt_buffer       = None
state            = State(default_shader)

def Init(w,h, pixel_size):
    global crt_buffer
    """
    One time initialisation of the screen
    """


    default_shader.Load('default',
                        uniforms = ('tex','translation','scale',
                                    'screen_dimensions',
                                    'using_textures'),
                        attributes = ('vertex_data',
                                      'tc_data',
                                      'colour_data'))

    crt_shader.Load('crt',
                    uniforms = ('tex','translation','scale',
                                'screen_dimensions','global_time'),
                    attributes = ('vertex_data',
                                  'tc_data'))

    crt_buffer = CrtBuffer(*pixel_size)

    #gbuffer = GeometryBuffer(w,h)
    #shadow_buffer = ShadowMapBuffer()


    glClearColor(0.0, 0.0, 0.0, 1.0)
    glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)

    #SetRenderDimensions(w,h,z_max)

    glEnable(GL_TEXTURE_2D)
    glEnable(GL_BLEND)
    glEnable(GL_DEPTH_TEST);
    glAlphaFunc(GL_GREATER, 0.25);
    glEnable(GL_ALPHA_TEST);
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

def ResetState():
    state.Reset()

def Translate(x,y,z):
    state.pos += Point(x,y)
    state.Update()

def Scale(x,y,z):
    state.scale = Point(x,y)
    state.Update()

def NewFrame():
    default_shader.Use()
    crt_buffer.BindForWriting()
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    # ui_buffers.Reset()
    # geom_shader.Use()
    # gbuffer.BindForWriting()
    glDepthMask(GL_TRUE)
    glClearColor(0.0, 0.0, 0.0, 1.0)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

def EndCrt():
    crt_shader.Use()
    glUniform1f(crt_shader.locations.global_time, globals.time/1000.0)
    crt_buffer.BindForReading(0)
    glClearColor(0.0, 0.0, 0.0, 1.0)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glEnableVertexAttribArray( crt_shader.locations.vertex_data );
    glEnableVertexAttribArray( crt_shader.locations.tc_data );
    #glUniform2f(crt_shader.locations.scale, 0.33333, 0.3333)
    glVertexAttribPointer( crt_shader.locations.vertex_data, 3, GL_FLOAT, GL_FALSE, 0, globals.screen_quadbuffer.vertex_data );
    glVertexAttribPointer( crt_shader.locations.tc_data, 2, GL_FLOAT, GL_FALSE, 0, drawing.constants.full_tc );

    glDrawElements(GL_QUADS,globals.screen_quadbuffer.current_size,GL_UNSIGNED_INT,globals.screen_quadbuffer.indices)
    glDisableVertexAttribArray( crt_shader.locations.vertex_data );
    glDisableVertexAttribArray( crt_shader.locations.tc_data );
    crt_buffer.Unbind()
    default_shader.Use()
    glDisable(GL_DEPTH_TEST)
    glAlphaFunc(GL_GREATER, 0);
    glClear(GL_DEPTH_BUFFER_BIT)


# def SetRenderDimensions(x,y,z):
#     geom_shader.dimensions = (x,y,z)

# def GetRenderDimensions():
#     return geom_shader.dimensions

def InitDrawing():
    """
    Should only need to be called once at the start (but after Init)
    to enable the full client state. We turn off and on again where necessary, but
    generally try to keep them all on
    """
    # shadow_shader.Use()
    # glUniform1i(shadow_shader.locations.displacement_map, gbuffer.TEXTURE_TYPE_DISPLACEMENT)
    # glUniform1i(shadow_shader.locations.colour_map  , gbuffer.TEXTURE_TYPE_DIFFUSE)
    # glUniform1i(shadow_shader.locations.normal_map  , gbuffer.TEXTURE_TYPE_NORMAL)
    # glUniform1i(shadow_shader.locations.occlude_map  , gbuffer.TEXTURE_TYPE_OCCLUDE)
    # glUniform3f(shadow_shader.locations.screen_dimensions, globals.screen_abs.x, globals.screen_abs.y, z_max)
    # glUniform3f(shadow_shader.locations.sb_dimensions, globals.screen_abs.x, globals.screen_abs.y, 1)
    # glUniform2f(shadow_shader.locations.light_dimensions, 256, 256)
    # light_shader.Use()
    # glUniform1i(light_shader.locations.displacement_map, gbuffer.TEXTURE_TYPE_DISPLACEMENT)
    # glUniform1i(light_shader.locations.colour_map  , gbuffer.TEXTURE_TYPE_DIFFUSE)
    # glUniform1i(light_shader.locations.normal_map  , gbuffer.TEXTURE_TYPE_NORMAL)
    # glUniform1i(light_shader.locations.occlude_map  , gbuffer.TEXTURE_TYPE_OCCLUDE)
    # glUniform1i(light_shader.locations.shadow_map  , gbuffer.TEXTURE_TYPE_SHADOW)
    # glUniform1f(light_shader.locations.light_radius, 400)
    # glUniform1f(light_shader.locations.light_intensity, 1)
    # glUniform3f(light_shader.locations.screen_dimensions, globals.screen_abs.x, globals.screen_abs.y, z_max)
    # #glUniform1f(light_shader.locations.ambient_level, 0.3)
    default_shader.Use()
    glUniform3f(default_shader.locations.screen_dimensions, globals.screen_abs.x, globals.screen_abs.y, z_max)
    glUniform1i(default_shader.locations.tex, 0)
    # geom_shader.Use()
    # glUniform1i(geom_shader.locations.tex, 0)
    # glUniform1i(geom_shader.locations.normal_tex, 1)
    # glUniform1i(geom_shader.locations.occlude_tex, 2)
    # glUniform1i(geom_shader.locations.displace_tex, 3)
    # glUniform3f(geom_shader.locations.screen_dimensions, globals.screen_abs.x, globals.screen_abs.y, z_max)
    crt_shader.Use()
    glUniform3f(crt_shader.locations.screen_dimensions, globals.screen.x, globals.screen.y, 10)
    glUniform1i(crt_shader.locations.tex, 0)
    glUniform2f(crt_shader.locations.translation, 0, 0)
    glUniform2f(crt_shader.locations.scale, 1, 1)


def DrawAll(quad_buffer,texture):
    """
    Draw a quadbuffer with with a vertex array, texture coordinate array, and a colour
    array
    """
    #if quad_buffer.is_ui:
    DrawAllNow(quad_buffer, texture, default_shader)
        #ui_buffers.Add(quad_buffer,texture)
    #    return
    #DrawAllNowNormals(quad_buffer,texture,geom_shader)

def DrawAllNowNormals(quad_buffer,texture,shader):
    glActiveTexture(GL_TEXTURE0)
    glBindTexture(GL_TEXTURE_2D, texture.texture)
    glActiveTexture(GL_TEXTURE1)
    glBindTexture(GL_TEXTURE_2D, texture.normal_texture)
    glActiveTexture(GL_TEXTURE2)
    glBindTexture(GL_TEXTURE_2D, texture.occlude_texture)
    glActiveTexture(GL_TEXTURE3)
    glBindTexture(GL_TEXTURE_2D, texture.displacement_texture)

    glUniform1i(shader.locations.using_textures, 1)

    glEnableVertexAttribArray( shader.locations.vertex_data );
    glEnableVertexAttribArray( shader.locations.tc_data );
    glEnableVertexAttribArray( shader.locations.normal_data );
    glEnableVertexAttribArray( shader.locations.occlude_data );
    glEnableVertexAttribArray( shader.locations.displace_data );
    glEnableVertexAttribArray( shader.locations.colour_data );

    glVertexAttribPointer( shader.locations.vertex_data, 3, GL_FLOAT, GL_FALSE, 0, quad_buffer.vertex_data );
    glVertexAttribPointer( shader.locations.tc_data, 2, GL_FLOAT, GL_FALSE, 0, quad_buffer.tc_data );
    glVertexAttribPointer( shader.locations.normal_data, 2, GL_FLOAT, GL_FALSE, 0, quad_buffer.tc_data );
    glVertexAttribPointer( shader.locations.occlude_data, 2, GL_FLOAT, GL_FALSE, 0, quad_buffer.tc_data );
    glVertexAttribPointer( shader.locations.displace_data, 2, GL_FLOAT, GL_FALSE, 0, quad_buffer.tc_data );
    glVertexAttribPointer( shader.locations.colour_data, 4, GL_FLOAT, GL_FALSE, 0, quad_buffer.colour_data );

    glDrawElements(GL_QUADS,quad_buffer.current_size,GL_UNSIGNED_INT,quad_buffer.indices)
    glDisableVertexAttribArray( shader.locations.vertex_data );
    glDisableVertexAttribArray( shader.locations.tc_data );
    glDisableVertexAttribArray( shader.locations.normal_data );
    glDisableVertexAttribArray( shader.locations.occlude_data );
    glDisableVertexAttribArray( shader.locations.displace_data );
    glDisableVertexAttribArray( shader.locations.colour_data );

def DrawAllNow(quad_buffer,texture,shader):
    #This is a copy paste from the above function, but this is the inner loop of the program, and we need it to be fast.
    #I'm not willing to put conditionals around the normal lines, so I made a copy of the function without them
    glActiveTexture(GL_TEXTURE0)
    glBindTexture(GL_TEXTURE_2D, texture.texture)
    glUniform1i(shader.locations.using_textures, 1)

    glEnableVertexAttribArray( shader.locations.vertex_data );
    glEnableVertexAttribArray( shader.locations.tc_data );
    glEnableVertexAttribArray( shader.locations.colour_data );

    glVertexAttribPointer( shader.locations.vertex_data, 3, GL_FLOAT, GL_FALSE, 0, quad_buffer.vertex_data );
    glVertexAttribPointer( shader.locations.tc_data, 2, GL_FLOAT, GL_FALSE, 0, quad_buffer.tc_data );
    glVertexAttribPointer( shader.locations.colour_data, 4, GL_FLOAT, GL_FALSE, 0, quad_buffer.colour_data );

    glDrawElements(quad_buffer.draw_type,quad_buffer.current_size,GL_UNSIGNED_INT,quad_buffer.indices)
    glDisableVertexAttribArray( shader.locations.vertex_data );
    glDisableVertexAttribArray( shader.locations.tc_data );
    glDisableVertexAttribArray( shader.locations.colour_data );


def DrawNoTexture(quad_buffer):
    """
    Draw a quadbuffer with only vertex arrays and colour arrays. We need to make sure that
    we turn the clientstate for texture coordinates back on after we're finished
    """
    #if quad_buffer.is_ui:
        #ui_buffers.Add(quad_buffer,None)
        #return
    DrawNoTextureNow(quad_buffer,default_shader)

def DrawNoTextureNow(quad_buffer,shader):

    glUniform1i(shader.locations.using_textures, 0)

    glEnableVertexAttribArray( shader.locations.vertex_data );
    glEnableVertexAttribArray( shader.locations.colour_data );

    glVertexAttribPointer( shader.locations.vertex_data, 3, GL_FLOAT, GL_FALSE, 0, quad_buffer.vertex_data );
    glVertexAttribPointer( shader.locations.colour_data, 4, GL_FLOAT, GL_FALSE, 0, quad_buffer.colour_data );

    glDrawElements(quad_buffer.draw_type,quad_buffer.current_size,GL_UNSIGNED_INT,quad_buffer.indices)

    glDisableVertexAttribArray( shader.locations.vertex_data );
    glDisableVertexAttribArray( shader.locations.colour_data );

def LineWidth(width):
    glEnable(GL_LINE_SMOOTH)
    glLineWidth(width)
