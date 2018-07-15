# -*- coding: utf-8 -*-
import json
import logging
import os

from tqdm import tqdm

from lp2jira.lp import lp
from lp2jira.config import config
from lp2jira.utils import clean_id, get_user_groups


def export_users():
    logging.info('===== Export: Users =====')

    project = lp.projects[config['launchpad']['project']]
    subscriptions = project.getSubscriptions()

    counter = 0
    for sub in tqdm(subscriptions, desc='Export users'):
        username = clean_id(sub.subscriber_link)
        try:
            user = User.create(username)
        except Exception as exc:
            logging.error('User %s export failed' % username)
            logging.exception(exc)
        else:
            user.export()
            counter += 1
    logging.info('Exported users: %s/%s' % (counter, len(subscriptions)))


def create_user(username):
    try:
        user = User.create(username)
    except Exception as exc:
        logging.error('User %s export failed' % username)
        logging.exception(exc)
        return False
    else:
        user.export()


class User:
    def __init__(self, name, display_name, email=None, user_groups=None, active=True):
        self.name = name
        self.display_name = display_name
        self.active = active
        self.user_groups = user_groups
        self.email = email

    @classmethod
    def create(cls, username):
        lp_user = lp.people[username]

        if not lp_user.hide_email_addresses and lp_user.preferred_email_address:
            email = lp_user.preferred_email_address.email
        else:
            email = None

        return cls(name=username, display_name=lp_user.display_name,
                   email=email, user_groups=get_user_groups())

    def export(self):
        filename = os.path.normpath('%s/%s_user.json' % (config['local']['users'], self.name))
        if os.path.exists(filename):
            logging.info('User %s already exists, skipping: %s' % (self.name, filename))
            return True

        with open(filename, 'w') as f:
            json.dump(self._dump(), f)

        logging.info('User %s export success' % self.name)
        return True

    def _dump(self):
        dmp = {
            'name': self.name,
            'fullname': self.display_name,
            'active': self.active
        }
        if self.user_groups:
            dmp['groups'] = self.user_groups

        if self.email:
            dmp['email'] = self.email
        return dmp
