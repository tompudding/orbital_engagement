import numpy as np
import time
import threading
import pygame
import pygame.locals
import multiprocessing
import globals

parent_conn, child_conn = multiprocessing.Pipe()

class Player(object):
    def callback(self, outdata, frames, time, status):
        if not self.playing:
            outdata.fill(0)
            return
        if self.pos + frames > len(self.tone):
            #wrapping
            start = self.tone[self.pos:self.pos+frames]
            self.pos = frames-len(start)
            end = self.tone[:self.pos]
            new = np.append(start,end)
        else:
            new = self.tone[self.pos:self.pos+frames]
            self.pos += frames
        outdata[:, 0] = new

    def input_thread(self, conn):
        while self.running:
            command = conn.recv()
            if command == 'd':
                self.running = False
            else:
                self.playing = True if command == '1' else False

    def run(self, conn):
        import sounddevice as sd
        import generate
        self.tone = generate.GenerateTone(freq=700, vol=1.0/400000)
        self.playing = False
        self.running = True
        self.pos = 0
        self.thread = threading.Thread(target=self.input_thread, args=(conn, ))
        self.thread.start()

        with sd.OutputStream(channels=1, callback=self.callback, samplerate=48000, latency='low') as stream:
            while self.running:
                sd.sleep(100)
        self.thread.join()

player = Player()
t = multiprocessing.Process(target=player.run, args=(child_conn, ))
t.start()

class Morse(object):
    def __init__(self):
        self.on_times = []

    def key_on(self, t):
        parent_conn.send('1')

    def key_off(self, t):
        parent_conn.send('0')
