import os

import json
import hashlib
import hmac
import time
import os
import subprocess

from flask import Flask, request
import sh
import requests

app = Flask(__name__)
app.config['GITHUB_WEBHOOK_SECRET'] = os.environ.get('GITHUB_WEBHOOK_SECRET')
app.config['GITHUB_ACCESS_TOKEN'] = os.environ.get('GITHUB_ACCESS_TOKEN')


github = requests.Session()
github.headers.update({
    'Content-Type': 'application/json',
    'Authorization': 'token {}'.format(app.config['GITHUB_ACCESS_TOKEN'])
})


@app.route('/webhook/', methods=['GET', 'POST'])
def webhook():
    if request.method == 'POST':
        event = request.headers['X-GitHub-Event']
        signature = request.headers['X-Hub-Signature']

        mac = hmac.new(app.config['GITHUB_WEBHOOK_SECRET'], msg=request.data, digestmod=hashlib.sha1)
        if not 'sha1={}'.format(mac.hexdigest()) == signature:
            return 'Invalid signature', 403

        if event == 'ping':
            return json.dumps({'msg': 'hi'})
        if event == 'push':
            lint()

        return '', 201


def lint():
    payload = request.json
    ref = payload['ref']

    status = {
        'state': 'pending',
        'description': 'Waiting for linting result',
        'context': 'linting'
    }
    response = github.post(
        payload['repository']['statuses_url'],
        json.dumps(status)
    )

    response.raise_for_status()
