import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, Response, abort, flash
import boto3
from botocore.exceptions import ClientError
import requests

BUCKET = os.environ.get('PASTE_BUCKET')
CAPTCHA_SECRET = os.environ.get('CAPTCHA_SECRET')
SESSION_SECRET = os.environ.get('SESSION_SECRET')

app = Flask(__name__)
app.secret_key = SESSION_SECRET

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/', methods=['POST'])
def post():
    code = request.form.get('code')
    if not code:
        return redirect(url_for('index'))
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

    return redirect(url_for('fetch', filename=filename))

@app.route('/p/<filename>', methods=['GET'])
def fetch(filename):
    if filename.endswith('.txt'):
        content_type = 'text/plain'
    elif filename.endswith('.html'):
        content_type = 'text/html'
    else:
        # other types not allowed
        abort(404)

    s3 = boto3.client('s3')
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=filename)
    except ClientError:
        abort(404)

    return Response(obj['Body'].read(), mimetype='text/plain')

if __name__ == "__main__":
    app.run()
