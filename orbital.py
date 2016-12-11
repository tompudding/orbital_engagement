import os, sys
import ui
import globals
import game_view
import drawing
import sounds
import pygame
import pygame.locals

from globals.types import Point


def Init():
    """Initialise everything. Run once on startup"""
    #w,h = (1600,1000)
    w,h = (1280,720)
    globals.tile_scale            = Point(1,1)
    globals.scale                 = Point(2,2)
    globals.screen_abs            = Point(w,h)
    globals.time_factor           = 0.01
    globals.pixels_to_units       = 100.0
    globals.units_to_pixels       = 1/globals.pixels_to_units
    globals.music_volume = 0.1
    globals.screen                = globals.screen_abs/globals.scale
    globals.screen_root           = ui.UIRoot(Point(0,0),globals.screen_abs)
    globals.mouse_screen          = Point(0,0)
    globals.quad_buffer           = drawing.QuadBuffer(16384, ui=True)
    globals.screen_texture_buffer = drawing.QuadBuffer(256, ui=True)
    globals.backdrop_buffer       = drawing.QuadBuffer(16, ui=True)
    globals.ui_buffer             = drawing.QuadBuffer(1024, ui=True)
    globals.nonstatic_text_buffer = drawing.QuadBuffer(131072, ui=True)
    globals.light_quads           = drawing.QuadBuffer(16384)
    globals.nightlight_quads      = drawing.QuadBuffer(16)
    globals.temp_mouse_light      = drawing.QuadBuffer(16)
    globals.colour_tiles          = drawing.QuadBuffer(131072)
    globals.line_buffer           = drawing.LineBuffer(131072)
    globals.screen_quadbuffer     = drawing.QuadBuffer(16)
    globals.tick_factor           = 500
    globals.screen.crt      = drawing.Quad(globals.screen_quadbuffer)
    bl = Point(90,100)
    tr = bl + Point(160,90)*2.87
    globals.screen.crt.SetVertices(bl, tr,0.01)


    globals.dirs = globals.types.Directories('resource')


    pygame.init()
    screen = pygame.display.set_mode((w,h),pygame.OPENGL|pygame.DOUBLEBUF)
    pygame.display.set_caption('Orbital Engagement')

    drawing.Init(globals.screen_abs.x,globals.screen_abs.y,(globals.screen))

    globals.backdrop_texture = drawing.texture.Texture('screen.png')
    globals.screen.backdrop = drawing.Quad(globals.backdrop_buffer, tc=drawing.constants.full_tc)
    globals.screen.backdrop.SetVertices(Point(0,0), globals.screen_abs, 10)

    globals.text_manager = drawing.texture.TextManager()


Init()

globals.time = pygame.time.get_ticks()
globals.current_view = globals.game_view = game_view.GameView()

done = False
last = 0
clock = pygame.time.Clock()
drawing.InitDrawing()

#a = globals.text_manager.Letter('A',drawing.texture.TextTypes.SCREEN_RELATIVE)
#a.SetVertices(Point(0,0), Point(1000,1000), 1000)

while not done:
    globals.time = t = pygame.time.get_ticks()*globals.tick_factor*0.001
    clock.tick(60)

    if t - last > 1000:
        #print 'FPS:',clock.get_fps()
        last = t


    drawing.NewFrame()

    globals.current_view.Update(t)
    globals.current_view.Draw()

    drawing.EndCrt()
    globals.text_manager.Draw()
    drawing.DrawAll( globals.backdrop_buffer, globals.backdrop_texture )
    globals.screen_root.Draw()
    globals.current_view.DrawFinal()
    pygame.display.flip()


    eventlist = pygame.event.get()
    for event in eventlist:
        if event.type == pygame.locals.QUIT:
            done = True
            break

        elif (event.type == pygame.KEYDOWN):
            key = event.key
            try:
                #Try to use the unicode field instead. If it doesn't work for some reason,
                #use the old value
                key = ord(event.unicode)
            except (TypeError,AttributeError):
                pass
            globals.current_view.KeyDown(key)
        elif (event.type == pygame.KEYUP):
            globals.current_view.KeyUp(event.key)
        else:

            try:
                pos = Point(float(event.pos[0])/globals.scale[0],globals.screen[1]-(float(event.pos[1])/globals.scale[1]))
            except AttributeError:
                continue

            if event.type == pygame.MOUSEMOTION:
                globals.mouse_screen = Point(event.pos[0],globals.screen_abs[1]-event.pos[1])
                rel = Point(event.rel[0],-event.rel[1])
                handled = globals.screen_root.MouseMotion(globals.mouse_screen,rel,False)
                if handled:
                    globals.current_view.CancelMouseMotion()
                globals.current_view.MouseMotion(pos,rel,True if handled else False)
            elif (event.type == pygame.MOUSEBUTTONDOWN):
                for layer in globals.screen_root,globals.current_view:
                    handled,dragging = layer.MouseButtonDown(pos,event.button)
                    if handled and dragging:
                        globals.dragging = dragging
                        break
                    if handled:
                        break

            elif (event.type == pygame.MOUSEBUTTONUP):
                for layer in globals.screen_root,globals.current_view:
                    handled,dragging = layer.MouseButtonUp(globals.mouse_screen,event.button)
                    if handled and not dragging:
                        globals.dragging = None
                    if handled:
                        break
