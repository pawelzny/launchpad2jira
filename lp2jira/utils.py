# -*- coding: utf-8 -*-
import json
import logging
import re

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


def translate_blueprint_status(spec):
    with open(config['mapping']['blueprint'], 'r') as f:
        mapping = json.load(f)

    for mapp in mapping:
        result = []
        for condition, value in mapp['conditions'].items():
            try:
                if isinstance(value, str):
                    value = value.lower()

                spec_v = getattr(spec, condition)
                if isinstance(spec_v, str):
                    spec_v = spec_v.lower()

                result.append(value == spec_v)
            except AttributeError as exc:
                logging.error(f'Blueprint do not have attribute: "{condition}"')
                logging.exception(exc)
        if all(result):
            return mapp['status']
    logging.error(f'Status cannot be mapped to blueprint: {spec.title}')
    return config['mapping']['blueprint_default']


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


def convert_custom_field_type(field_type, value):
    t = field_type.split(':')[-1].lower()

    if 'string' in t or 'text' in t:
        return str(value)

    if 'bool' in t:
        return bool(value)

    if 'float' in t:
        return float(value)

    if 'int' in t:
        return int(value)

    return value


def json_dump(data, file):
    json.dump(data, file, indent=2, sort_keys=True)


def prepare_attachment_name(name):
    for old in [':', ' ']:
        name = name.replace(old, '_')
    return name


def get_user_data_from_activity_changed(value):
    if value is None:
        return '', None

    user_data = value.rsplit(' (', 1)
    return user_data[0], user_data[1][:-1]
