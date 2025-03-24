#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A series of very basic functions used in other tools
"""

def p_colorize(text, color_code):
    """Add color to terminal output"""
    return f"\033[{color_code}m{text}\033[0m"

def p_error(message):
    """Print error message in red"""
    print(f"    {p_colorize('ERROR:', '31')} {message}")

def p_ok(message):
    """Print ok message in green"""
    print(f"       {p_colorize('OK:', '32')} {message}")

def p_warning(message):
    """Print warning message in yellow"""
    print(f"  {p_colorize('WARNING:', '33')} {message}")
