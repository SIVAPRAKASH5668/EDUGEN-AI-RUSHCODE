from flask import Blueprint

bp = Blueprint('notegen', __name__)

from . import routes