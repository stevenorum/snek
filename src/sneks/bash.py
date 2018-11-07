#!/usr/bin/env python

# https://misc.flogisoft.com/bash/tip_colors_and_formatting
SHELL_COLORS = {
    'RED':'\033[91m',
    'GREEN':'\033[92m',
    'YELLOW':'\033[93m',
    'BLUE':'\033[94m',
    'PURPLE':'\033[95m',
    'WHITE':'\033[97m',
    'RESET':'\033[0m',
}

def color_text(s, c):
    return '{}{}{}'.format(SHELL_COLORS.get(c.upper(), SHELL_COLORS["BLUE"]), s, SHELL_COLORS["RESET"])

def blue_text(s):
    return color_text(s, "BLUE")

def print_blue(s):
    return print(blue_text(s))

def white_text(s):
    return color_text(s, "WHITE")

def print_white(s):
    return print(white_text(s))

def purple_text(s):
    return color_text(s, "PURPLE")

def print_purple(s):
    return print(purple_text(s))

def green_text(s):
    return color_text(s, "GREEN")

def print_green(s):
    return print(green_text(s))

def yellow_text(s):
    return color_text(s, "YELLOW")

def print_yellow(s):
    return print(yellow_text(s))

def red_text(s):
    return color_text(s, "RED")

def print_red(s):
    return print(red_text(s))
