# -*- coding: utf-8 -*-
import configparser

from launchpadlib.launchpad import Launchpad

config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
config.read('export.cfg')

lp = Launchpad.login_with('LP2JIRA', config['launchpad']['service'],
                          launchpadlib_dir=config['launchpad']['cache_dir'],
                          version='devel', credentials_file='token')
