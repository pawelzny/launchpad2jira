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
        if create_user(username):
            counter += 1
    logging.info('Exported users: %s/%s' % (counter, len(subscriptions)))


def create_user(username):
    filename = os.path.normpath('%s/%s_user.json' % (config['local']['users'], username))
    if os.path.exists(filename):
        logging.info('User %s already exists, skipping: %s' % (username, filename))
        return True

    try:
        lp_user = lp.people[username]
    except Exception as e:
        logging.error('User %s export failed' % username)
        logging.exception(e)
        return False
    else:
        email = None
        if not lp_user.hide_email_addresses and lp_user.preferred_email_address:
            email = lp_user.preferred_email_address.email

        user = {
            'name': username,
            'fullname': lp_user.display_name,
            'active': True,
        }

        user_groups = get_user_groups()
        if user_groups:
            user['groups'] = user_groups
        if email:
            user['email'] = email

        with open(filename, 'w') as f:
            json.dump(user, f)

        logging.info('User %s export success' % username)
        return True
