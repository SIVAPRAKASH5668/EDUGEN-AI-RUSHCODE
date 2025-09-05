from flask import Blueprint

bp = Blueprint('video2pdf', __name__)

from . import routes  # Import routes after creating blueprint