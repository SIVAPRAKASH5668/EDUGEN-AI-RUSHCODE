from flask import Blueprint

bp = Blueprint('memck', __name__)

from . import routes  # Import routes after creating blueprint