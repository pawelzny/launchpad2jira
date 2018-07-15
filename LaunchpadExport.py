#!/usr/bin/env python
# coding: utf-8
import logging
import os

from lp2jira.config import config


def main():
    from lp2jira.blueprint import ExportBlueprints
    from lp2jira.export import compile_export_file
    from lp2jira.issue import ExportBugs
    from lp2jira.user import ExportSubscribers

    logging.info('===== Export start =====')
    ExportSubscribers().run()
    ExportBugs().run()
    ExportBlueprints().run()
    logging.info('===== Compile export file =====')
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
