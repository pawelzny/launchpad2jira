# -*- coding: utf-8 -*-
import json
import logging
import os
import re

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from lp2jira.config import config
from lp2jira.export import Export
from lp2jira.issue import Issue
from lp2jira.lp import lp
from lp2jira.utils import bug_template, translate_status


class Blueprint(Issue):
    @classmethod
    def create(cls, name):
        project = lp.projects[config['launchpad']['project']]
        spec = project.getSpecification(name=name)

        if spec.is_complete:
            status = translate_status('Fix Released')
        elif spec.is_started and not spec.is_complete:
            status = translate_status('In Progress')
        else:
            status = translate_status('New')

        description = f'{spec.summary}\n\n{spec.whiteboard}\n\n{spec.workitems_text}'

        # TODO: issue type must not be hardcoded
        return cls(issue_id=name, status=status, owner=spec.owner, title=spec.title,
                   desc=description, priority=spec.priority,
                   issue_type='Story', created=spec.date_created,
                   assignee=spec.assignee)

    def export(self):
        self._export_related_users()

        filename = os.path.normpath(f'{config["local"]["issues"]}/{self.issue_id}_blueprint.json')
        if os.path.exists(filename):
            logging.info(f'Blueprint {self.issue_id} already exists, skipping: {filename}')
            return True

        export_bug = bug_template()
        export_bug['projects'][0]['issues'] = [self._dump()]
        export_bug['links'] = []
        with open(filename, 'w') as f:
            json.dump(export_bug, f)

        logging.debug(f'Blueprint {self.issue_id} export success')
        return True


class ExportBlueprint(Export):
    def __init__(self):
        super().__init__(entity=Blueprint)


class ExportBlueprints(ExportBlueprint):
    def run(self):
        logging.info('===== Export: Blueprints =====')

        url = f'https://blueprints.launchpad.net/{config["launchpad"]["project"]}/+specs?show=all'
        res = requests.get(url)
        soup = BeautifulSoup(res.text, 'html.parser')
        specs = soup.find_all(href=lambda x: x and re.compile('\+spec/').search(x))

        counter = 0
        for a in tqdm(specs, desc='Export blueprints'):
            name = a.get('href').split('/')[-1]
            if super().run(name=name):
                counter += 1

        logging.info('Exported blueprints: %s/%s' % (counter, len(specs)))
