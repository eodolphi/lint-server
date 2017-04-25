import os
from urlparse import urljoin

import json
import hashlib
import hmac

from flask import Flask, request
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
            pending()

        return '', 201


@app.route('/repos/<user>/<repo>/statuses/<sha>', methods=['POST'])
def status(user, repo, sha):
    result = request.get_data().strip()

    if result:
        status = {
            'state': 'failure',
            'description': 'Linting failed',
            'context': 'linting'
        }
    else:
        status = {
            'state': 'success',
            'description': 'No style issues found',
            'context': 'linting'
        }

    response = github.post(
        'https://api.github.com/repos/{user}/{repo}/statuses/{sha}'.format(
            user=user, repo=repo, sha=sha
        ),
        json.dumps(status)
    )

    response.raise_for_status()
    return json.dumps(status), 200


def pending():
    payload = request.json
    ref = payload['head_commit']['id']

    status = {
        'state': 'pending',
        'description': 'Waiting for linting result',
        'context': 'linting'
    }
    response = github.post(
        payload['repository']['statuses_url'].format(sha=ref),
        json.dumps(status)
    )

    response.raise_for_status()


if __name__ == "__main__":
        app.run()
