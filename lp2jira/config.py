# -*- coding: utf-8 -*-
import configparser

config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
config.read('export.cfg')
