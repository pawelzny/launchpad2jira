# -*- coding: utf-8 -*-
from launchpadlib.launchpad import Launchpad

from lp2jira.config import config

lp = Launchpad.login_with('LP2JIRA', config['launchpad']['service'],
                          launchpadlib_dir=config['launchpad']['cache_dir'],
                          version='devel')
