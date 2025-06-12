#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A series of very basic functions used in other tools
"""

from datetime import datetime, timedelta
from inspect import signature

def p_colorize(text, color_code):
    """Adds color to terminal output"""
    return f"\033[{color_code}m{text}\033[0m"

def p_error(message):
    """Prints an error message in red"""
    print(f"    {p_colorize('ERROR:', '31')} {message}")

def p_ok(message):
    """Prints an ok message in green"""
    print(f"       {p_colorize('OK:', '32')} {message}")

def p_warning(message):
    """Prints a warning message in yellow"""
    print(f"  {p_colorize('WARNING:', '33')} {message}")

def p_filter_args(func, kwargs):
    """filters arguments dynamically"""
    return {k : v for k, v in kwargs.items() if k in signature(func).parameters}

def p_strip_None(d : dict):
    """
    recursively strips None values from a nested dict
    return a strip dict
    """
    if isinstance(d, dict):
        return {k : v for k, v in ((k, p_strip_None(v)) for k, v in d.items()) if v is not None}
    elif isinstance(d, list):
        return [y for y in [p_strip_None(i) for i in d] if y is not None] or None
    return d if d is not None else None

def p_convert_julian_day_to_gregorian_date(julian_day : int, ref='cnes'):
    """
    convert julian day to gregorian date
    return gregorian date in datetime format
    """
    if ref == 'cnes':
        gregorian_date = datetime(1950, 1, 1) + timedelta(days=julian_day)
    else:
        raise ValueError
    return gregorian_date.strftime('%Y-%m-%d')

def p_convert_gregorian_date_to_julian_day(gregorian_date : str, ref='cnes'):
    gregorian_date = datetime.strptime(gregorian_date, '%Y-%m-%d')
    if ref == 'cnes':
        return (gregorian_date - datetime(1950, 1, 1)).days
    else:
        raise ValueError

# def p_calculate_number_of_days_between_two_dates(date : str, date_to : str):
#     """
#     calculate the number of days between two dates in str format 'y-m-d'
#     return a integer of the number of days
#     """
#     date, date_to = datetime.strptime(date, '%Y-%m-%d'), datetime.strptime(date_to, '%Y-%m-%d')
#     _timedelta = date_to - date
#     return _timedelta.days


