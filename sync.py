#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from future.standard_library import install_aliases

install_aliases()

from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import HTTPError

import os
import urllib2
import json
from datetime import datetime

from flask import Flask
from flask import Response

app = Flask(__name__)

# Here's the magic
@app.route('/sync')
def sync():

    data = {
        "channel": os.environ['SLACK_NOTIFY_CHANNEL'],
        "text": "Notified of EveryPolitician data update, beginning sync to CKAN!",
    }

    try:
        req = Request(os.environ['SLACK_BOT_URL'])
        req.add_header('Content-Type', 'application/json')

        response = urlopen(req, json.dumps(data).encode('utf-8'))
    except HTTPError as e:
        error_message = e.read()
        print(error_message)

    EP_COUNTRIES_URL = os.environ['EP_COUNTRIES_URL']
    CKAN_API_ENDPOINT = os.environ['CKAN_API_ENDPOINT']
    CKAN_API_KEY = os.environ['CKAN_API_KEY']
    CKAN_EP_ORG = os.environ['CKAN_EP_ORG']
    CKAN_LICENSE_ID = os.environ['CKAN_LICENSE_ID']

    # This will force metadata and resource updates, even if versions match
    FORCE_UPDATE = bool(int(os.environ['FORCE_UPDATE']))

    # This will force a complete rebuild of resources
    FORCE_RESOURCE_REBUILD = bool(int(os.environ['FORCE_RESOURCE_REBUILD']))

    response = urllib2.urlopen(EP_COUNTRIES_URL)
    ep_countries = json.load(response)

    if FORCE_UPDATE:
        print('RUNNING WITH FORCED UPDATES')

    if FORCE_RESOURCE_REBUILD:
        print('RUNNING WITH FORCED RESOURCE REBUILDS')

    def sync_to_ckan():

        for country in ep_countries:
            yield '<p>Working on country ' + country['name'].encode('utf-8') + '.</p>'
            print('Country ' + country['name'].encode('utf-8'))

            for legislature in country['legislatures']:

                name = country['slug'].lower() + '-' + legislature['slug'].lower()
                title = country['name'].encode('utf-8') + ': ' + legislature['name'].encode('utf-8')

                print('\tLegislature ' + legislature['name'].encode('utf-8'))
                print('\t\t' + name)
                print('\t\t' + title)

                # We start out assuming resources need updating.
                update_resources = True

                # Build up the dataset we want. This will be patched in, so things we
                # don't specify here remain unchanged (like resources, which are
                # resolved later on)

                dataset = {
                    'name': name,
                    'title': title,
                    'state': 'active',
                    'notes': 'Data on the people within the "' + legislature['name'] + '" legislature of ' + country['name'] + '.',
                    'owner_org': CKAN_EP_ORG,
                    'author': 'EveryPolitician',
                    'author_email': 'team@everypolitician.org',
                    'maintainer': 'EveryPolitician',
                    'maintainer_email': 'team@everypolitician.org',
                    'license_id': CKAN_LICENSE_ID,
                    'url': 'http://everypolitician.org/' + country['slug'].lower() + '/',
                    'version': legislature['lastmod'],
                    'tags': [
                        {'name': 'everypolitician'}
                    ]
                }

                if FORCE_RESOURCE_REBUILD:
                    dataset['resources'] = []

                # This is where we do gnarly things

                # Does the dataset actually exist in the first place?

                try:
                    package_get_data = {
                        'id': name
                    }
                    request = urllib2.Request(
                        CKAN_API_ENDPOINT + 'action/package_show?' + urlencode(package_get_data))
                    request.add_header('Authorization', CKAN_API_KEY)
                    response = urllib2.urlopen(request)

                    assert response.code is 200

                    response_json = json.load(response)
                    existing_dataset = response_json['result']

                    # All going well, got a 200, resource exists!

                    # Do we actually need to update this?

                    if (str(existing_dataset['version']) != str(dataset['version']) or FORCE_UPDATE):

                        try:
                            print('\t\t\tNeeds update, patching!')
                            print('\t\t\tCurrent: ' + existing_dataset['version'] + ' New: ' + dataset['version'])

                            # We need to add the ID
                            dataset['id'] = existing_dataset['id']
                            data_string = urllib2.quote(json.dumps(dataset))

                            request = urllib2.Request(
                                CKAN_API_ENDPOINT + 'action/package_patch')
                            request.add_header('Authorization', CKAN_API_KEY)
                            response = urllib2.urlopen(request, data_string)

                            assert response.code is 200

                            response_json = json.load(response)
                            existing_dataset = response_json['result']

                        except urllib2.URLError, e:
                            print('\t\t\tERROR: ' + str(e.code))
                            print('\t\t\t' + e.read())
                            raise

                    else:
                        print('\t\t\tMetadata version matches, no update needed!')
                        update_resources = False

                except urllib2.URLError, e:

                    if e.code == 404:
                        print('\t\t\tDoes not exist, creating dataset!')
                        try:
                            data_string = urllib2.quote(json.dumps(dataset))
                            request = urllib2.Request(
                                CKAN_API_ENDPOINT + 'action/package_create')
                            request.add_header('Authorization', CKAN_API_KEY)
                            response = urllib2.urlopen(request, data_string)

                        except urllib2.URLError, e:
                            print('\t\t\t\tERROR: ' + str(e.code))
                            print('\t\t\t\t' + e.read())
                            raise

                        assert response.code is 200

                        response_json = json.load(response)
                        existing_dataset = response_json['result']
                    else:
                        # This wasn't a 404, so it's probably dangerous
                        print('\t\t\tERROR: ' + str(e.code))
                        print('\t\t\t' + e.read())
                        raise

                # By this point, we definitely have a dataset object, and it's
                # definitely up to date.

                # Here we do some gnarly magic to create a simple list for turning a
                # name into a CKAN ID. CKAN resources cannot (apparently) have custom
                # IDs.

                if update_resources:

                    print('\t\t\tUpdating resources...')

                    resources = []

                    resources.append({
                        'id': 'popolo',
                        'package_id': existing_dataset['id'],
                        'name': 'All Data as Popolo JSON',
                        'format': 'JSON',
                        'mimetype': 'application/json',
                        'url': legislature['popolo_url'],
                        'last_modified': datetime.fromtimestamp(int(legislature['lastmod'])).isoformat()
                    })

                    for period in legislature['legislative_periods']:

                        if 'end_date' in period:
                            date_string = period['start_date'] + ' to ' + period['end_date']
                        else:
                            date_string = 'From ' + period['start_date']

                        resources.append({
                            'package_id': existing_dataset['id'],
                            'id': 'period-' + period['slug'],
                            'name': period['name'],
                            'format': 'CSV',
                            'mimetype': 'text/csv',
                            'url': period['csv_url'],
                            'description': date_string,
                            'last_modified': datetime.fromtimestamp(int(legislature['lastmod'])).isoformat()
                        })

                    for resource in resources:
                        print('\t\t\t\t' + resource['name'].encode('utf-8'))
                        data_string = urllib2.quote(json.dumps(resource))
                        try:
                            request = urllib2.Request(
                                CKAN_API_ENDPOINT + 'action/resource_create')
                            request.add_header('Authorization', CKAN_API_KEY)
                            response = urllib2.urlopen(request, data_string)
                            assert response.code is 200
                        except urllib2.URLError, e:
                            print('\t\t\t\tERROR: ' + str(e.code))
                            print('\t\t\t\t' + e.read())

    return Response(sync_to_ckan(), 'text/html')

# Fire it up!
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
