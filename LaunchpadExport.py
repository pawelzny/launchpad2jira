#!/usr/bin/env python
# coding: utf-8
import logging
import os
import sys

from lp2jira.config import config


def main():
    from lp2jira.blueprint import ExportBlueprints
    from lp2jira.export import ExportCompile
    from lp2jira.issue import ExportBugs
    from lp2jira.user import ExportSubscribers

    logging.info('===== Export start =====')
    ExportSubscribers().run()
    ExportBugs().run()
    ExportBlueprints().run()
    logging.info('===== Compile export file =====')
    ExportCompile().run()
    logging.info('===== Export complete =====')


if __name__ == '__main__':
    logging.basicConfig(filename=config['logging']['filename'],
                        format=config['logging']['format'],
                        level=config['logging']['level'])

    for directory in config['local'].values():
        if not os.path.exists(directory):
            os.mkdir(directory)

    try:
        main()
    except KeyboardInterrupt:
        msg = "Export has been stopped by user"
        print(msg)
        logging.info(msg)
        sys.exit(0)
