# -*- coding: utf-8 -*-
import logging
import os
import re

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from lp2jira.config import config, lp
from lp2jira.export import Export
from lp2jira.issue import Issue
from lp2jira.utils import bug_template, json_dump, translate_blueprint_status


class Blueprint(Issue):
    issue_type = config['mapping']['blueprint_type']

    @classmethod
    def create(cls, name):
        project = lp.projects[config['launchpad']['project']]
        spec = project.getSpecification(name=name)

        status = translate_blueprint_status(spec)
        description = f'{spec.summary}\n\n{spec.whiteboard}\n\n{spec.workitems_text}'
        custom_fields = Issue.create_custom_fields(spec)
        # TODO: issue type can't be hardcoded
        return cls(issue_id=name, status=status, owner=spec.owner, title=spec.title,
                   desc=description, priority=spec.priority,
                   created=spec.date_created.isoformat(), tags=[],
                   assignee=spec.assignee, custom_fields=custom_fields, affected_versions=[])

    def export(self):
        self._export_related_users()

        filename = self.filename(self.issue_id)
        if self.exists(filename):
            logging.debug(f'Blueprint {self.issue_id} already exists, skipping: "{filename}"')
            return True

        export_bug = bug_template()
        export_bug['projects'][0]['issues'] = [self._dump()]
        export_bug['links'] = []
        with open(filename, 'w') as f:
            json_dump(export_bug, f)

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

        failed_specs = []
        counter = 0
        for index, spec in enumerate(tqdm(specs, desc='Export blueprints')):
            name = spec.get('href').split('/')[-1]
            if super().run(name=name):
                counter += 1
            else:
                failed_specs.append(f'index: {index}, name: {name}')

        logging.info(f'Exported blueprints: {counter}/{len(specs)}')
        if failed_specs:
            fail_log = '\n'.join(failed_specs)
            logging.info(f'Failed blueprints:\n{fail_log}')
