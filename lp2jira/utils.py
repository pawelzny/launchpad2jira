# -*- coding: utf-8 -*-
import json

from lp2jira.config import config


def clean_id(item_id):
    tail = item_id.split('/')[-1]
    return tail.lstrip('~')


def translate_status(status):
    with open(config['mapping']['issue'], 'r') as f:
        mapping = json.load(f)
    return mapping[status.title()]


def translate_priority(priority):
    with open(config['mapping']['priority'], 'r') as f:
        mapping = json.load(f)
    return mapping[priority.title()]


def bug_template():
    return {
        'users': [],
        'links': [],
        'projects': [
            {
                'name': config['jira']['project'],
                'key': config['jira']['key'],
                'type': 'software',
                'issues': [],
            },
        ],
    }


def get_user_groups():
    return [g.strip() for g in config['jira']['groups'].split(',')]
