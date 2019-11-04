import argparse
import os
import sys

import semver
import yaml

CHART_PATH = os.path.join('dss', 'chart', 'wq2dss', 'Chart.yaml')


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('--bump_part', choices=['patch', 'minor', 'major'],
                        help='indicate which version part to bump', default='patch')
    parser.add_argument('--chart_location', default=CHART_PATH, help='The path to Chart.yaml that needs to be updated')
    parser.add_argument('--app_version', default=None, help='The new appVersion that should be used')
    args = parser.parse_args()
    with open(args.chart_location, 'r') as input_chart:
        current_chart = yaml.safe_load(input_chart)

    current_version = current_chart['version']
    curr_version_info = semver.VersionInfo.parse(current_version)
    next_version_info = None
    if args.bump_part == 'patch':
        next_version_info = curr_version_info.bump_patch()
    elif args.bump_part == 'minor':
        next_version_info = curr_version_info.bump_minor()
    elif args.bump_part == 'major':
        next_version_info = curr_version_info.bump_major()
    else:
        return 1

    current_chart['version'] = str(next_version_info)
    if args.app_version:
        current_chart['appVersion'] = args.app_version
    with open(args.chart_location, 'w') as output_chart:
        yaml.dump(current_chart, output_chart)

    return 0


if __name__ == '__main__':
    sys.exit(main())
