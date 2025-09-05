from flask import Blueprint

bp = Blueprint('rag', __name__)

from . import routes  # Import routes after creating blueprint