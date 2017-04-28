import os
import json
import hashlib
import hmac

from flask import Flask, request, url_for, render_template
from flask_redis import FlaskRedis
import requests

app = Flask(__name__)
app.config['GITHUB_WEBHOOK_SECRET'] = os.environ.get('GITHUB_WEBHOOK_SECRET')
app.config['GITHUB_ACCESS_TOKEN'] = os.environ.get('GITHUB_ACCESS_TOKEN')
app.config['REDIS_URL'] = os.environ.get('REDIS_URL')

redis_store = FlaskRedis(app)


github = requests.Session()
github.headers.update({
    'Content-Type': 'application/json',
    'User-Agent': 'Linter-server',
    'Authorization': 'token {}'.format(app.config['GITHUB_ACCESS_TOKEN'])
})


class Report(object):
    def __init__(self, text):
        self.raw = text

    def save(self, user, repo, sha):
        redis_store.set(self._redis_key(user, repo, sha), self.raw)

    @staticmethod
    def _redis_key(user, repo, sha):
        return '{}-{}-{}'.format(user, repo, sha)

    @classmethod
    def get(cls, user, repo, sha):
        return cls(redis_store.get(cls._redis_key(user, repo, sha)))

    @property
    def status(self):
        if not self.raw:
            return 'success'
        else:
            return 'failure'

    @property
    def issues(self):
        return [line.split(':') for line in self.raw.split("\n")]

    @property
    def summary(self):
        if not self.raw:
            return 'No issues found'
        else:
            return 'Found {} styling issues'.format(
                len(self.raw.split("\n"))
            )


@app.route('/webhook/', methods=['GET', 'POST'])
def webhook():
    if request.method == 'POST':
        event = request.headers['X-GitHub-Event']
        signature = request.headers['X-Hub-Signature']

        mac = hmac.new(
            app.config['GITHUB_WEBHOOK_SECRET'],
            msg=request.data,
            digestmod=hashlib.sha1
        )
        if not 'sha1={}'.format(mac.hexdigest()) == signature:
            return 'Invalid signature', 403

        if event == 'ping':
            return json.dumps({'msg': 'hi'})
        if event == 'push':
            pending()

        return '', 201


@app.route('/repos/<user>/<repo>/statuses/<sha>', methods=['POST'])
def status(user, repo, sha):
    report = Report(request.get_data().strip())

    report.save(user, repo, sha)

    status = {
        'state': report.status,
        'description': report.summary,
        'context': 'linting',
        'target_url': url_for(
            'report', user=user, repo=repo, sha=sha, _external=True
        )
    }

    response = github.post(
        'https://api.github.com/repos/{user}/{repo}/statuses/{sha}'.format(
            user=user, repo=repo, sha=sha
        ),
        json.dumps(status)
    )

    print response.content, status
    response.raise_for_status()

    return json.dumps(status), 200


@app.route('/reports/<user>/<repo>/statuses/<sha>')
def report(user, repo, sha):
    report = Report.get(user, repo, sha)

    context = {
        'issues': report.issues,
        'status': report.status,
        'user': user,
        'repo': repo,
        'sha': sha
    }
    return render_template("report.html", **context)


def pending():
    payload = request.json
    ref = payload['head_commit']['id']

    status = {
        'state': 'pending',
        'description': 'Waiting for report',
        'context': 'linting'
    }
    response = github.post(
        payload['repository']['statuses_url'].format(sha=ref),
        json.dumps(status)
    )

    response.raise_for_status()


if __name__ == "__main__":
        app.run()
