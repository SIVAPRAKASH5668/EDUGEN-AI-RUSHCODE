from flask import Blueprint

bp = Blueprint('main_site', __name__)

from . import routes