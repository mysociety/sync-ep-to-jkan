#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from future.standard_library import install_aliases

install_aliases()

import os

from flask import Flask
from flask import Response
from flask import request

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


app = Flask(__name__)


# Here's the magic
@app.route('/sync', methods=['GET', 'POST'])
def sync():

    def sync_to_jkan(payload):

        yield '<h1>EveryPolitician to JKAN Sync</h1>'

        yield '<h2>Payload</h2>'

        yield '<pre>'

        print('PAYLOAD:')
        print(payload)

        yield pprint.pformat(payload)

        yield '</pre>'

        yield '<h2>Actions</h2>'

        data = {
            "channel": SLACK_NOTIFY_CHANNEL,
            "text": "Notified of EveryPolitician data update, beginning sync to JKAN!",
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
                return

            yield '<p>Working on country ' + country['name'].encode('utf-8') + '.</p>'
            print('Country ' + country['name'].encode('utf-8'))

            for legislature in country['legislatures']:

                yield '<p>Working on legislature ' + legislature['name'].encode('utf-8') + '.</p>'
                print('\tLegislature ' + legislature['name'].encode('utf-8'))

                name = 'everypolitician-' + country['slug'].lower() + '-' + legislature['slug'].lower()
                title = country['name'].encode('utf-8') + ' — ' + legislature['name'].encode('utf-8')

                content = """---
schema: default
title: Politician Data: """ + title + """
organization: """ + EP_ORG_NAME + """
notes: Data on the people within the """ + legislature['name'].encode('utf-8') + """ legislature of """ + country['name'].encode('utf-8') + """.
resources:
  - name: How To Use The Data
    url: 'http://docs.everypolitician.org/use_the_data.html'
    format: info
  - name: View on EveryPolitician
    url: 'http://everypolitician.org/""" + country['slug'].lower() + """/'
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
  - name: """ + period['name'].encode('utf-8') + """: """ + date_string.encode('utf-8') + """
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

            yield '<p>Committed changes.</p>'
            print('Committed changes')

            # Push it!
            repo.remotes.origin.push()

            yield '<p>Pushed changes.</p>'
            print('Pushed changes')

        else:

            yield '<p>Skipping commit, there is no difference.</p>'
            print('Skipping commit, there is no difference')

    return Response(
        response=sync_to_jkan(request.get_json()),
        mimetype='text/html'
    )

# Fire it up!
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
