#!/usr/bin/env python
# coding: utf-8
import logging
import os

from lp2jira.config import config


def main():
    from lp2jira.blueprint import export_blueprints
    from lp2jira.export import compile_export_file
    from lp2jira.issue import export_issues
    from lp2jira.user import export_users

    logging.info('===== Export start =====')
    export_users()
    export_issues()
    export_blueprints()
    compile_export_file()
    logging.info('===== Export complete =====')


if __name__ == '__main__':
    logging.basicConfig(filename=config['logging']['filename'],
                        format=config['logging']['format'],
                        level=config['logging']['level'])

    for directory in config['local'].values():
        if not os.path.exists(directory):
            os.mkdir(directory)

    main()
