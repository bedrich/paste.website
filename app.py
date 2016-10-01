import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, Response, abort, flash, make_response
import boto3
from botocore.exceptions import ClientError
import requests
import datetime

BUCKET = os.environ.get('PASTE_BUCKET')
CAPTCHA_SECRET = os.environ.get('CAPTCHA_SECRET')
SESSION_SECRET = os.environ.get('SESSION_SECRET')
COOKIE_NAME = "imnotacomputer"
COOKIE_SECRET = os.environ.get('COOKIE_SECRET')
LEGACY_URL_PREFIX = os.environ.get('LEGACY_URL_PREFIX')

app = Flask(__name__)
app.secret_key = SESSION_SECRET

@app.route('/', methods=['GET'])
def index():
    skip_captcha = request.cookies.get(COOKIE_NAME) == COOKIE_SECRET
    return render_template('index.html', skip_captcha=skip_captcha)

@app.route('/', methods=['POST'])
def post():
    code = request.form.get('code')
    if not code:
        return redirect(url_for('index'))

    if request.cookies.get(COOKIE_NAME) != COOKIE_SECRET:
        r = requests.post(
            'https://www.google.com/recaptcha/api/siteverify',
            data={
                'secret': CAPTCHA_SECRET,
                'response': request.form.get('g-recaptcha-response')
            }
        )
        if r.status_code != 200:
            abort(400)
        if not r.json()['success']:
            flash('Invalid CAPTCHA')
            return redirect(url_for('index'))

    filename = "{}.txt".format(uuid.uuid4())
    s3 = boto3.client('s3')
    try:
        s3.put_object(Bucket=BUCKET, Key=filename, Body=code)
    except ClientError:
        # something went wrong
        abort(400)

    resp = make_response(redirect(url_for('fetch', filename=filename)))
    # valid captcha? no need for future captchas (for a year)
    expires = datetime.datetime.utcnow() + datetime.timedelta(days=365)
    resp.set_cookie(COOKIE_NAME, value=COOKIE_SECRET, expires=expires, httponly=True)
    return resp

@app.route('/p/<filename>', methods=['GET'])
def fetch(filename):
    if filename.endswith('.txt'):
        content_type = 'text/plain'
    elif filename.endswith('.html'):
        content_type = 'text/html'
    else:
        # other types not allowed
        abort(404)

    if ".." in filename or "/" in filename:
        # belt and suspenders on URL "hacking"
        abort(404)

    s3 = boto3.client('s3')
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=filename)
    except ClientError:
        # not found. additionally try to fetch the old roguecoders one:
        if LEGACY_URL_PREFIX:
            r = requests.get("{}/{}".format(LEGACY_URL_PREFIX, filename))
            if r.status_code == 200:
                return Response(r.content, mimetype=content_type)
        abort(404)

    return Response(obj['Body'].read(), mimetype=content_type)

if __name__ == "__main__":
    app.run()
