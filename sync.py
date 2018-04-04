#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from future.standard_library import install_aliases

install_aliases()

import os

from urllib.request import urlopen, Request
from urllib.error import HTTPError

import urllib2
import json
from datetime import datetime

from git import Repo
from git import Actor

import pprint


EP_COUNTRIES_URL = os.environ['EP_COUNTRIES_URL']
EP_MAINTAINER_EMAIL = os.environ['EP_MAINTAINER_EMAIL']
EP_MAINTAINER_NAME = os.environ['EP_MAINTAINER_NAME']
EP_MORE_INFO_URL = os.environ['EP_MORE_INFO_URL']
EP_ORG_NAME = os.environ['EP_ORG_NAME']
GITHUB_JKAN_URL = os.environ['GITHUB_JKAN_URL']
REPO_DIR = os.environ['REPO_DIR']
SLACK_BOT_URL = os.environ['SLACK_BOT_URL']
SLACK_NOTIFY_CHANNEL = os.environ['SLACK_NOTIFY_CHANNEL']


def sync_to_jkan():

    print('EveryPolitician to JKAN Sync')

    print('Actions')

    data = {
        "channel": SLACK_NOTIFY_CHANNEL,
        "text": "Running scheduled sync of EveryPolitician to JKAN!",
    }

    try:
        req = Request(SLACK_BOT_URL)
        req.add_header('Content-Type', 'application/json')

        response = urlopen(req, json.dumps(data).encode('utf-8'))
    except HTTPError as e:
        error_message = e.read()
        print(error_message)

    # Check to see if the repo directory exists.
    if not os.path.isdir(REPO_DIR):

        # No repo? Clone the JKAN directory.
        Repo.clone_from(GITHUB_JKAN_URL, REPO_DIR)

    # Initialise the repository object
    repo = Repo(REPO_DIR)

    # Move the HEAD to the gh-pages branch
    pages_branch = repo.create_head('gh-pages')
    repo.head.reference = pages_branch
    # Reset the index and working tree to match the pointed-to commit
    repo.head.reset(index=True, working_tree=True)

    # Pull so we're up to date
    repo.remotes.origin.pull()

    # Get the EP countries
    response = urllib2.urlopen(EP_COUNTRIES_URL)
    ep_countries = json.load(response)

    for country in ep_countries:

        if country['slug'] == 'UK':
            print('Skipping UK!')

        else:

            print('COUNTRY: ' + country['name'].encode('utf-8'))

            for legislature in country['legislatures']:

                print('\tLegislature ' + legislature['name'].encode('utf-8'))

                name = 'everypolitician-' + country['slug'].lower() + '-' + legislature['slug'].lower()
                title = country['name'].encode('utf-8') + ' — ' + legislature['name'].encode('utf-8')

                content = """---
schema: default
title: >-
  Politician Data: """ + title + """
organization: """ + EP_ORG_NAME + """
notes: >-
  Data on the people within the """ + legislature['name'].encode('utf-8') + """ legislature of """ + country['name'].encode('utf-8') + """.
resources:
  - name: How To Use The Data
    url: 'http://docs.everypolitician.org/use_the_data.html'
    format: info
  - name: View on EveryPolitician
    url: 'http://everypolitician.org/""" + country['slug'].lower().encode('utf-8') + """/'
    format: info
  - name: All Data as Popolo JSON
    url: >-
      """ + legislature['popolo_url'].encode('utf-8') + """
    format: json"""

                for period in legislature['legislative_periods']:

                    if 'end_date' in period:
                        date_string = period['start_date'] + ' to ' + period['end_date']
                    else:
                        date_string = 'From ' + period['start_date']

                    content += """
  - name: >-
      """ + period['name'].encode('utf-8') + """: """ + date_string.encode('utf-8') + """
    url: >-
      """ + period['csv_url'].encode('utf-8') + """
    format: csv"""

                content += """
  - name: Python
    url: 'https://github.com/everypolitician/everypolitician-popolo-python'
    format: library
  - name: Ruby
    url: 'https://github.com/everypolitician/everypolitician-popolo'
    format: library
  - name: R
    url: 'https://github.com/ajparsons/everypoliticianR'
    format: library
last_modified: """ + datetime.fromtimestamp(int(legislature['lastmod'])).isoformat() + """
license: ''
category:
  - """ + country['name'].encode('utf-8') + """
  - People
  - Groups & Bodies
maintainer: """ + EP_MAINTAINER_NAME + """
maintainer_email: """ + EP_MAINTAINER_EMAIL + """
more_info: """ + EP_MORE_INFO_URL + """
---
"""

            with open(REPO_DIR + '/_datasets/' + name + '.md', 'w') as file:
                file.write(content)

    # Add all the tracked files to the repo. Do this using native git.
    repo.git.add(A=True)

    # Commit the index.
    index = repo.index

    if index.diff('HEAD'):

        author = Actor("EveryPolitician", "team@everypolitician.org")
        committer = Actor("DataBot", "data@mysociety.org")
        # commit by commit message and author and committer
        index.commit("Update EveryPolitician data", author=author, committer=committer)

        print('Committed changes')

        # Push it!
        repo.remotes.origin.push()

        print('Pushed changes')

    else:

        print('Skipping commit, there is no difference')

sync_to_jkan()
