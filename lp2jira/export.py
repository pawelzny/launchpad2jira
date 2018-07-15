# -*- coding: utf-8 -*-
import json
import logging
import os
from json import JSONDecodeError

from tqdm import tqdm

from lp2jira.config import config
from lp2jira.utils import bug_template


def compile_export_file():
    logging.info('===== Compile export file =====')

    export_bug = bug_template()
    export_bug['projects'][0]['issues'] = []
    for filename in tqdm(os.listdir(config['local']['issues']), desc='Compile issues'):
        with open(os.path.join(config['local']['issues'], filename), 'r') as f:
            try:
                issue = json.load(f)
            except JSONDecodeError:
                logging.error('Export error in issue: %s' % filename)
                continue
        export_bug['projects'][0]['issues'].extend(issue['projects'][0]['issues'])
        export_bug['links'].extend(issue['links'])

    for filename in tqdm(os.listdir(config['local']['users']), desc='Compile users'):
        with open(os.path.join(config['local']['users'], filename), 'r') as f:
            try:
                user = json.load(f)
            except JSONDecodeError:
                logging.error('Export error in user: %s' % filename)
                continue
        export_bug['users'].append(user)

    logging.info('Compiled issues: %s', len(export_bug['projects'][0]['issues']))
    logging.info('Compiled links: %s', len(export_bug['links']))
    logging.info('Compiled users: %s', len(export_bug['users']))

    filename = os.path.join(config['local']['export'], config['jira']['filename'])
    with open(filename, 'w') as f:
        json.dump(export_bug, f)

    logging.info('Exported data saved in: %s' % filename)
