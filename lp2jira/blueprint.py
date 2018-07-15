# -*- coding: utf-8 -*-
import json
import logging
import os
import re

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from lp2jira import user
from lp2jira.config import config
from lp2jira.lp import lp
from lp2jira.utils import bug_template, clean_id, translate_priority, translate_status


def export_blueprints():
    logging.info('===== Export: Blueprints =====')
    project = lp.projects[config['launchpad']['project']]

    url = 'https://blueprints.launchpad.net/%s/+specs?show=all' % config['launchpad']['project']
    res = requests.get(url)
    soup = BeautifulSoup(res.text, 'html.parser')

    specs = soup.find_all(href=lambda x: x and re.compile('\+spec/').search(x))
    counter = 0
    export_user = user.ExportUser()
    for a in tqdm(specs, desc='Export blueprints'):
        name = a.get('href').split('/')[-1]

        try:
            spec = project.getSpecification(name=name)
            export_user(username=clean_id(spec.owner.name))
            if spec.assignee:
                export_user(username=clean_id(spec.assignee.name))
        except Exception as e:
            logging.exception(e)
            continue

        filename = os.path.normpath('%s/%s_blueprint.json' % (config['local']['issues'], name))
        if os.path.exists(filename):
            counter += 1
            logging.info('Blueprint %s already exists, skipping: %s' % (name, filename))
            continue

        if spec.is_complete:
            status = translate_status('Fix Released')
        elif spec.is_started and not spec.is_complete:
            status = translate_status('In Progress')
        else:
            status = translate_status('New')

        issue = {
            'externalId': name,
            'status': status,
            'reporter': spec.owner.display_name,
            'summary': spec.title,
            'description': '%s\n\n%s\n\n%s' % (spec.summary, spec.whiteboard, spec.workitems_text),
            'priority': translate_priority(spec.priority),
            'issueType': 'Story',
            'created': spec.date_created.isoformat(),
        }
        if spec.assignee:
            issue['assignee'] = spec.assignee.display_name

        export_bug = bug_template()
        export_bug['projects'][0]['issues'] = [issue]
        export_bug['links'] = []
        with open(filename, 'w') as f:
            json.dump(export_bug, f)
        counter += 1

        logging.info('Blueprint %s export success' % name)
    logging.info('Exported blueprints: %s/%s' % (counter, len(specs)))
