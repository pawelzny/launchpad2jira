#!/usr/bin/env python
# coding: utf-8
import argparse
import logging
import os
import sys

from lp2jira.config import config


def main(export_bugs=True, export_blueprints=True, update_bugs=False, verify_update=False):
    from lp2jira.blueprint import ExportBlueprints
    from lp2jira.export import ExportCompile
    from lp2jira.issue import ExportBugs, UpdateBugs
    from lp2jira.user import ExportSubscribers

    if verify_update:
        logging.info('===== Verify start =====')
        UpdateBugs().verify_update()
        logging.info('===== Verify complete =====')
    else:
        logging.info('===== Export start =====')
        ExportSubscribers().run()
        if export_bugs:
            ExportBugs().run()
        if export_blueprints:
            ExportBlueprints().run()

        logging.info('===== Compile export file =====')
        ExportCompile().run()
        logging.info('===== Export complete =====')
        if update_bugs:
            logging.info('===== Update start =====')
            UpdateBugs().run()
            logging.info('===== Update complete =====')


if __name__ == '__main__':
    logging.basicConfig(filename=config['logging']['filename'],
                        format=config['logging']['format'],
                        level=config['logging']['level'])

    for directory in config['local'].values():
        if not os.path.exists(directory):
            os.mkdir(directory)

    parser = argparse.ArgumentParser()
    parser.add_argument('--only-bugs', help='Export only bugs', action='store_true')
    parser.add_argument('--only-blueprints', help='Export only blueprints', action='store_true')
    parser.add_argument('--update-bugs', help='Update bugs', action='store_true')
    parser.add_argument('--verify-update', help='Verify update', action='store_true')
    args = parser.parse_args()

    try:
        if args.verify_update:
            if not args.only_bugs and not args.only_blueprints and not args.update_bugs:
                main(export_bugs=False, export_blueprints=False, verify_update=True)
            else:
                raise Exception('You can only use --verify-update by itself')
        else:
            if args.only_bugs and args.only_blueprints:
                raise Exception('You can use only one of --only-bugs or --only-blueprints')
            if args.update_bugs:
                main(update_bugs=True)
            elif args.only_bugs:
                main(export_blueprints=False)
            elif args.only_blueprints:
                main(export_bugs=False)
            else:
                main()
    except KeyboardInterrupt:
        msg = "Execution has been stopped by user"
        print(msg)
        logging.info(msg)
        sys.exit(0)
