# routes/route.py
from flask import Blueprint, render_template, redirect, url_for

from . import bp

@bp.route('/')
def index():
    return render_template('index.html')
