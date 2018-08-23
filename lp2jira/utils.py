# -*- coding: utf-8 -*-
import json

from lp2jira.config import config, lp


def clean_id(item_id):
    tail = item_id.split('/')[-1]
    return tail.lstrip('~')


def get_owner(person_link):
    username = clean_id(person_link)
    return lp.people[username]


def translate_status(status):
    with open(config['mapping']['issue'], 'r') as f:
        mapping = json.load(f)
    try:
        return mapping[status.title()]
    except KeyError:
        return status


def translate_priority(priority):
    with open(config['mapping']['priority'], 'r') as f:
        mapping = json.load(f)
    try:
        return mapping[priority.title()]
    except KeyError:
        return priority


def bug_template():
    return {
        'users': [],
        'links': [],
        'projects': [
            {
                'name': config['jira']['project'],
                'key': config['jira']['key'],
                'type': 'software',
                'versions': [],
                'issues': [],
            },
        ],
    }


def get_user_groups():
    return [g.strip() for g in config['jira']['groups'].split(',')]


def get_custom_fields():
    with open(config['mapping']['custom_fields'], 'r') as f:
        mapping = json.load(f)
    return mapping
