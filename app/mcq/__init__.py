from flask import Blueprint

bp = Blueprint('mcq', __name__)

from . import routes