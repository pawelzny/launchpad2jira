# -*- coding: utf-8 -*-
import logging
import os

from tqdm import tqdm

from lp2jira.config import config, lp
from lp2jira.export import Export
from lp2jira.utils import clean_id, get_user_groups, json_dump


class User:
    def __init__(self, name, display_name, email=None, user_groups=None, active=True):
        self.name = name
        self.display_name = display_name
        self.active = active
        self.user_groups = user_groups
        self.email = email

    @classmethod
    def create(cls, username):
        try:
            lp_user = lp.people[username]

            display_name = lp_user.display_name
            if not lp_user.hide_email_addresses and lp_user.preferred_email_address:
                email = lp_user.preferred_email_address.email
            else:
                email = None
        except Exception as exc:
            logging.warning(f"Failed to get user data for {username}")
            logging.warning(exc, exc_info=True)

            display_name = username
            email = None

        return cls(name=username, display_name=display_name,
                    email=email, user_groups=get_user_groups())
            

    @staticmethod
    def filename(username):
        return os.path.normpath(os.path.join(config["local"]["users"], f'{username}.json'))

    @staticmethod
    def exists(username):
        return os.path.exists(User.filename(username))

    def export(self):
        filename = self.filename(self.name)
        if self.exists(filename):
            logging.debug(f'User {self.display_name} already exists, skipping: "{filename}"')
            return True

        with open(filename, 'w') as f:
            json_dump(self._dump(), f)

        logging.debug(f'User User {self.display_name} export success')
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


class ExportUser(Export):
    def __init__(self):
        super().__init__(entity=User)


class ExportSubscribers(ExportUser):
    def run(self):
        logging.info('===== Export: Subscribers =====')

        project = lp.projects[config['launchpad']['project']]
        subscriptions = project.getSubscriptions()

        counter = 0
        for sub in tqdm(subscriptions, desc='Export subscribers'):
            username = clean_id(sub.subscriber_link)
            if User.exists(username):
                counter += 1
                continue

            if super().run(username):
                counter += 1

        logging.info(f'Exported subscribers: {counter}/{len(subscriptions)}')
