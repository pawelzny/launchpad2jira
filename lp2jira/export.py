# -*- coding: utf-8 -*-
import json
import logging
import os
from json import JSONDecodeError

from tqdm import tqdm

from lp2jira.config import config
from lp2jira.utils import bug_template, json_dump


class Export:
    def __init__(self, entity):
        self.entity = entity

    def __call__(self, *args, **kwargs):
        return self.run(*args, **kwargs)

    def run(self, *args, **kwargs):
        try:
            entity = self.entity.create(*args, **kwargs)
        except Exception as exc:
            logging.error(f'{self.entity.__name__} export failed for {args} {kwargs}')
            logging.exception(exc)
            return False
        else:
            entity.export()
            return True


class ExportCompile(Export):
    def __init__(self):
        super().__init__(entity=None)

    def run(self):
        logging.info('===== Compile export file =====')

        export_bug = bug_template()
        export_links = bug_template()


        for filename in tqdm(os.listdir(config['local']['issues']), desc='Compile issues'):
            with open(os.path.join(config['local']['issues'], filename), 'r') as f:
                try:
                    issue = json.load(f)
                except JSONDecodeError:
                    logging.error(f'Export error in issue: {filename}')
                    continue
            export_bug['projects'][0]['issues'].extend(issue['projects'][0]['issues'])
            export_bug['projects'][0]['versions'].extend(issue['projects'][0]['versions'])
            export_links['links'].extend(issue['links'])

        for filename in tqdm(os.listdir(config['local']['users']), desc='Compile users'):
            with open(os.path.join(config['local']['users'], filename), 'r') as f:
                try:
                    user = json.load(f)
                except JSONDecodeError:
                    logging.error('Export error in user: %s' % filename)
                    continue
            export_bug['users'].append(user)

        logging.info(f'===== Export summary =====')
        logging.info(f'Compiled issues: {len(export_bug["projects"][0]["issues"])}')
        logging.info(f'Compiled links: {len(export_bug["links"])}')
        logging.info(f'Compiled users: {len(export_bug["users"])}')

        filename = os.path.join(config['local']['export'], config['jira']['issues'])
        links_file = os.path.join(config['local']['export'], config['jira']['links'])

        with open(filename, 'w') as f:
            json_dump(export_bug, f)

        with open(links_file, 'w') as f:
            json_dump(export_links, f)

        logging.info(f'Exported data saved in: {filename}')
