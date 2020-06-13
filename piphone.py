#!/bin/env python

import pickle
import fnmatch
# For raspberry pi hardware + Find OS Path for images
import os
import pygame
from pygame import *
from time import sleep
import serial

busy = False
threadExited = False
screenMode = 0  # Current screen mode; default = viewfinder
phone_call = 1
screenModePrior = -1  # Prior screen mode (for detecting changes)
iconPath = 'icons'  # Subdirectory containing UI bitmaps (PNG format)
numeric = 0  # number from numeric keypad
number_string = ""
motorRunning = 0
motorDirection = 0
returnScreen = 0
shutter_pin = 17
motor_pin_A = 18
motor_pin_B = 27
motor_pin = motor_pin_A
currentframe = 0
frame_count = 100
settling_time = 0.2
shutter_length = 0.2
interval_delay = 0.2

dict_idx = "Interval"
v = {"Pulse": 100,
     "Interval": 3000,
     "Images": 150}

icons = []  # This list gets populated at startup


# UI classes ---------------------------------------------------------------
# The list of Icons is populated at runtime from the contents of the 'icons' directory.

class Icon:

    def __init__(self, name):
        self.name = name
        try:
            self.bitmap = pygame.image.load(iconPath + '/' + name + '.png')
        except:
            pass


class Button:

    def __init__(self, rect, **kwargs):
        self.rect = rect  # Bounds
        self.color = None  # Background fill color, if any
        self.iconBg = None  # Background Icon (atop color fill)
        self.iconFg = None  # Foreground Icon (atop background)
        self.bg = None  # Background Icon name
        self.fg = None  # Foreground Icon name
        self.callback = None  # Callback function
        self.value = None  # Value passed to callback
        for key_obj, value in kwargs.items():
            if key_obj == 'color':
                self.color = value
            elif key_obj == 'bg':
                self.bg = value
            elif key_obj == 'fg':
                self.fg = value
            elif key_obj == 'cb':
                self.callback = value
            elif key_obj == 'value':
                self.value = value

    def selected(self, pos_obj):
        x1 = self.rect[0]
        y1 = self.rect[1]
        x2 = x1 + self.rect[2] - 1
        y2 = y1 + self.rect[3] - 1
        if ((pos_obj[0] >= x1) and (pos_obj[0] <= x2) and
                (pos_obj[1] >= y1) and (pos_obj[1] <= y2)):
            if self.callback:
                if self.value is None:
                    self.callback()
                else:
                    self.callback(self.value)
            return True
        return False

    def draw(self, screen_obj):
        if self.color:
            screen_obj.fill(self.color, self.rect)
        if self.iconBg:
            screen_obj.blit(self.iconBg.bitmap,
                            (self.rect[0] + (self.rect[2] - self.iconBg.bitmap.get_width()) / 2,
                             self.rect[1] + (self.rect[3] - self.iconBg.bitmap.get_height()) / 2))
        if self.iconFg:
            screen_obj.blit(self.iconFg.bitmap,
                            (self.rect[0] + (self.rect[2] - self.iconFg.bitmap.get_width()) / 2,
                             self.rect[1] + (self.rect[3] - self.iconFg.bitmap.get_height()) / 2))

    def set_bg(self, name):
        if name is None:
            self.iconBg = None
        else:
            for icon in icons:
                if name == icon.name:
                    self.iconBg = icon
                    break


# UI callbacks -------------------------------------------------------------
# These are defined before globals because they're referenced by items in
# the global buttons[] list.


def numeric_callback(n):  # Pass 1 (next setting) or -1 (prev setting)
    global screenMode
    global number_string
    global phone_call
    if n < 10 and screenMode == 0:
        number_string = number_string + str(n)
    elif n == 10 and screenMode == 0:
        number_string = number_string[:-1]
    elif n == 12:
        if screenMode == 0:
            if len(number_string) > 0:
                serial_port.write(str('AT\r').encode('ascii'))
                print(serial_port.readlines())

                new_number_string = str(number_string + ';\r').encode('ascii')

                serial_port.write(new_number_string)
                print(serial_port.readlines())
                screenMode = 1
        else:
            print("Hanging Up...")
            serial_port.write(str("AT\r").encode('ascii'))
            serial_port.write(str("ATH\r").encode('ascii'))
            screenMode = 0
        if len(number_string) > 0:
            numeric_obj = int(number_string)
            v[dict_idx] = numeric_obj


buttons = [
    # Screen 0 for numeric input
    [Button((30, 0, 320, 60), bg='box'),
     Button((30, 60, 60, 60), bg='1', cb=numeric_callback, value=1),
     Button((90, 60, 60, 60), bg='2', cb=numeric_callback, value=2),
     Button((150, 60, 60, 60), bg='3', cb=numeric_callback, value=3),
     Button((30, 110, 60, 60), bg='4', cb=numeric_callback, value=4),
     Button((90, 110, 60, 60), bg='5', cb=numeric_callback, value=5),
     Button((150, 110, 60, 60), bg='6', cb=numeric_callback, value=6),
     Button((30, 160, 60, 60), bg='7', cb=numeric_callback, value=7),
     Button((90, 160, 60, 60), bg='8', cb=numeric_callback, value=8),
     Button((150, 160, 60, 60), bg='9', cb=numeric_callback, value=9),
     Button((30, 210, 60, 60), bg='star', cb=numeric_callback, value=0),
     Button((90, 210, 60, 60), bg='0', cb=numeric_callback, value=0),
     Button((150, 210, 60, 60), bg='hash', cb=numeric_callback, value=0),
     Button((180, 260, 60, 60), bg='del2', cb=numeric_callback, value=10),
     Button((90, 260, 60, 60), bg='call', cb=numeric_callback, value=12)],
    # Screen 1 for numeric input
    [Button((30, 0, 320, 60), bg='box'),
     Button((90, 260, 60, 60), bg='hang', cb=numeric_callback, value=12)]
]


def save_settings():
    global v
    try:
        outfile = open('pi_phone.pkl', 'wb')
        # Use a dictionary (rather than pickling 'raw' values) so
        # the number & order of things can change without breaking.
        pickle.dump(v, outfile)
        outfile.close()
    except:
        pass


def load_settings():
    global v
    try:
        infile = open('pi_phone.pkl', 'rb')
        v = pickle.load(infile)
        infile.close()
    except:
        pass


# Initialization -----------------------------------------------------------

# Init framebuffer/touchscreen environment variables
# Specific to Rasberri Pi Hardware
# Uncomment for Rasberry pi vs Laptop
# os.putenv('SDL_VIDEODRIVER', 'fbcon')
# os.putenv('SDL_FBDEV', '/dev/fb1')
# os.putenv('SDL_MOUSEDRV', 'TSLIB')
# os.putenv('SDL_MOUSEDEV', '/dev/input/touchscreen')

# # Init py game and screen
pygame.init()
# py game.mouse.set_visible(False)
# Hide mouse on RasPi
# Show mouse on Linux
pygame.mouse.set_visible(True)

modes = pygame.display.list_modes(16)
# screen = pygame.display.set_mode(modes[0], FULLSCREEN, 16)
# screen = pygame.display.set_mode(modes)

# Linux laptop display
screen = pygame.display.set_mode(size=(240, 320), flags=0, depth=0, display=0)

# Load all icons at startup.
for file in os.listdir(iconPath):
    if fnmatch.fnmatch(file, '*.png'):
        icons.append(Icon(file.split('.')[0]))
# Assign Icons to Buttons, now that they're loaded
for s in buttons:  # For each screenful of buttons...
    for b in s:  # For each button on screen...
        for i in icons:  # For each icon...
            if b.bg == i.name:  # Compare names; match?
                b.iconBg = i  # Assign Icon to Button
                b.bg = None  # Name no longer used; allow garbage collection
            if b.fg == i.name:
                b.iconFg = i
                b.fg = None

load_settings()  # Must come last; fiddles with Button/Icon states

img = pygame.image.load("icons/PiPhone.png")

if img is None or img.get_height() < 240:  # Letterbox, clear background
    screen.fill(0)
if img:
    screen.blit(img,
                ((240 - img.get_width()) / 2,
                 (320 - img.get_height()) / 2))
pygame.display.update()
sleep(2)

print('Initialising Modem..')
# Laptop vs raspberry pie
serial_port = serial.Serial("/dev/ttyUSB0", 9600, timeout=0.5)
serial_port.write(str("AT\r").encode('ascii'))
print(serial_port.readlines())
serial_port.write(str("ATE0\r").encode('ascii'))
print(serial_port.readlines())
serial_port.write(str("AT\r").encode('ascii'))

response = serial_port.readlines()
print(response)

while True:

    # Process touchscreen input
    while True:
        screen_change = 0
        for event in pygame.event.get():
            if event.type is MOUSEBUTTONDOWN:
                pos = pygame.mouse.get_pos()
                for b in buttons[screenMode]:
                    if b.selected(pos):
                        break
                screen_change = 1

            # if screenMode >= 1 or screenMode != screenModePrior: break
        if screen_change == 1 or screenMode != screenModePrior:
            break

    if img is None or img.get_height() < 240:
        screen.fill(0)
    if img:
        screen.blit(img,
                    ((240 - img.get_width()) / 2,
                     (320 - img.get_height()) / 2))

    # Overlay buttons on display and update
    for i, b in enumerate(buttons[screenMode]):
        b.draw(screen)
    if screenMode == 0:
        my_font = pygame.font.SysFont("Arial", 40)
        label = my_font.render(number_string, 1, (255, 255, 255))
        screen.blit(label, (10, 2))
    else:
        my_font = pygame.font.SysFont("Arial", 35)
        label = my_font.render("Calling", 1, (255, 255, 255))
        screen.blit(label, (10, 80))
        my_font = pygame.font.SysFont("Arial", 35)
        label = my_font.render(number_string + "...", 1, (255, 255, 255))
        screen.blit(label, (10, 120))

    pygame.display.update()
    screenModePrior = screenMode
