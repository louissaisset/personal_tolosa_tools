"""Modules"""
import os
import sys
import logging
from datetime import datetime as dt

def set_logging(log_level, log_path=''):
    """
    set log level and create the object logging
    """
    
    # creation of the log folder
    if not os.path.exists(log_path):
        os.makedirs(log_path)
    log_filepath = '/'.join([log_path, f"{dt.now().strftime('%Y-%m-%dT%I%M%S')}.log"])
    
    # dict of debug levels
    level = {'debug': logging.DEBUG,
            'info': logging.INFO,
            'warning': logging.WARNING,
            'error': logging.ERROR,
            'critical': logging.CRITICAL}

    fileFormatter = logging.Formatter(fmt='[%(asctime)s] %(levelname)s : %(message)s',
                                      datefmt='%Y-%m-%d %I:%M:%S')
    
    handler = logging.FileHandler(log_filepath)
    handler.setFormatter(fileFormatter)

    screenFormatter = logging.Formatter('%(levelname)s : %(message)s')
    stdo = logging.StreamHandler(stream=sys.stdout)
    stdo.setFormatter(screenFormatter)

    logging.basicConfig(handlers=[handler, stdo], level=level[log_level])